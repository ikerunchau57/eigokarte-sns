"""全自動投稿のエントリポイント。

  python -m src.run prepare            その日の文章・画像・BGM・動画を作る（未作成なら）
  python -m src.run post --slot morning|noon|evening
  python -m src.run note               note記事を投稿
  python -m src.run auto               現在時刻(JST)から何をするか自動判断（GitHub Actions用）

DRY_RUN=1 で実際には投稿せず内容だけ表示します。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import sys
from pathlib import Path

import yaml

from . import content as content_mod
from . import music, video, visuals
from .publishers import instagram, note, threads, x
from .publishers.common import NotConfigured, PublishError, dry_run

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
STATE = ROOT / "state"
PUBLIC = ROOT / "public"
JST = dt.timezone(dt.timedelta(hours=9))
SLOTS = ["morning", "noon", "evening"]


def today() -> str:
    return os.environ.get("RUN_DATE") or dt.datetime.now(JST).strftime("%Y-%m-%d")


def load_yaml(name: str) -> dict:
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


def day_dir(date: str) -> Path:
    return PUBLIC / date


def media_url(date: str, filename: str) -> str:
    base = os.environ.get("MEDIA_BASE_URL", "").rstrip("/")
    if not base:
        raise PublishError("MEDIA_BASE_URL が未設定です（GitHub Pages のURL）")
    return f"{base}/{date}/{filename}"


# ---------- テーマ選び ----------

def pick_topic(date: str) -> tuple[str, str]:
    topics = load_yaml("topics.yaml")["categories"]
    history_path = STATE / "history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    used = {h["topic"] for h in history}
    pool = [(c, t) for c, ts in topics.items() for t in ts if t not in used]
    if not pool:  # 一巡したらリセット
        pool = [(c, t) for c, ts in topics.items() for t in ts]
    # 直前と同じカテゴリは避ける
    last_cat = history[-1]["category"] if history else None
    preferred = [p for p in pool if p[0] != last_cat] or pool
    rng = random.Random(date)
    return rng.choice(preferred)


def record_history(date: str, category: str, topic: str) -> None:
    STATE.mkdir(exist_ok=True)
    path = STATE / "history.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    history = [h for h in history if h["date"] != date]
    history.append({"date": date, "category": category, "topic": topic})
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def promo_for(date: str, brand: dict) -> dict:
    links = brand.get("promo_links") or [{"title": brand["name"], "url": brand["url"]}]
    return links[dt.date.fromisoformat(date).toordinal() % len(links)]


# ---------- 生成 ----------

def prepare(date: str, content_json: Path | None = None) -> Path:
    out = day_dir(date)
    cpath = out / "content.json"
    if (out / "reel.mp4").exists() and cpath.exists():
        print(f"[prepare] {date} は作成済み")
        return out
    out.mkdir(parents=True, exist_ok=True)
    brand = load_yaml("brand.yaml")

    if content_json:  # テスト用: 既存のJSONから作る
        c = content_mod.load(content_json)
        category, topic = "テスト", c.topic
    elif cpath.exists():
        c = content_mod.load(cpath)
        category, topic = "再開", c.topic
    else:
        facts = load_yaml("facts.yaml").get("facts", [])
        category, topic = pick_topic(date)
        print(f"[prepare] テーマ: 【{category}】{topic}")
        c = content_mod.generate(brand, facts, category, topic, date, promo_for(date, brand))
        record_history(date, category, topic)
    cpath.write_text(c.model_dump_json(indent=2), encoding="utf-8")
    (out / "note.md").write_text(f"# {c.note_title}\n\n{c.note_body_markdown}\n", encoding="utf-8")

    images = visuals.render_all(c, brand, out)
    seed = int(hashlib.sha256(date.encode()).hexdigest(), 16) % (2**31)
    seconds = video.duration_for(len(images["video_frames"]))
    bgm = music.pick_or_make(out, seconds, seed, ROOT / "assets")
    video.build(images["video_frames"], bgm, out / "reel.mp4")
    for f in images["video_frames"]:  # 動画用の縦長フレームとBGMは公開不要
        f.unlink()
    if bgm.parent == out:
        bgm.unlink()
    print(f"[prepare] 完了: {out}")
    return out


# ---------- 投稿 ----------

def _posted_log(date: str) -> dict:
    p = day_dir(date) / "posted.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _mark(date: str, key: str, value: str) -> None:
    log = _posted_log(date)
    log[key] = value
    (day_dir(date) / "posted.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_once(date: str, key: str, fn) -> None:
    """同じ投稿を二重に出さない。失敗しても他SNSは続行する。"""
    if key in _posted_log(date):
        print(f"[skip] {key} は投稿済み")
        return
    try:
        result = fn()
        if not dry_run():
            _mark(date, key, str(result))
        print(f"[ok] {key}: {result}")
    except NotConfigured as e:
        print(f"[skip] {key}: {e}")
    except Exception as e:  # noqa: BLE001
        print(f"[error] {key}: {e}", file=sys.stderr)
        _failures.append(key)


_failures: list[str] = []


def post_slot(date: str, slot: str) -> None:
    out = prepare(date)
    c = content_mod.load(out / "content.json")
    brand = load_yaml("brand.yaml")
    i = SLOTS.index(slot)

    x_text = c.x_posts[i]
    if slot in brand.get("x_link_slots", []):
        x_text = f"{x_text}\n{promo_for(date, brand)['url']}"
    _run_once(date, f"x_{slot}", lambda: x.post(x_text))

    th_text = c.threads_posts[i]
    th_image = media_url(date, "x_image.jpg") if slot == "morning" and not dry_run() else None
    _run_once(date, f"threads_{slot}", lambda: threads.post(th_text, th_image))

    caption = c.instagram_caption
    if slot == "noon":
        n = len(c.slides)
        urls = [media_url(date, f"carousel_{k:02d}.jpg") for k in range(1, n + 1)] if not dry_run() else [""] * n
        _run_once(date, "instagram_carousel", lambda: instagram.post_carousel(urls, caption))
    if slot == "evening":
        url = media_url(date, "reel.mp4") if not dry_run() else ""
        cover = media_url(date, "carousel_01.jpg") if not dry_run() else None
        _run_once(date, "instagram_reel", lambda: instagram.post_reel(url, caption, cover))


def post_note(date: str) -> None:
    out = prepare(date)
    c = content_mod.load(out / "content.json")
    brand = load_yaml("brand.yaml")
    promo = promo_for(date, brand)
    body = f"{c.note_body_markdown}\n\n---\n\n{brand['name']}（{brand['tagline']}）\n{brand['url']}\n今日のおすすめ: {promo['title']}\n{promo['url']}\n"
    _run_once(date, "note", lambda: note.post(c.note_title, body, out / "_screens"))


def auto(date: str) -> None:
    """GitHub Actions の cron から呼ばれる。JSTの時刻で枠を決める。"""
    hour = dt.datetime.now(JST).hour
    slot = os.environ.get("FORCE_SLOT") or ("morning" if hour < 11 else "noon" if hour < 16 else "evening")
    post_slot(date, slot)
    if slot == "evening":
        post_note(date)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["prepare", "post", "note", "auto"])
    ap.add_argument("--slot", choices=SLOTS)
    ap.add_argument("--date", default=None)
    ap.add_argument("--content-json", type=Path, default=None, help="テスト用: 生成済みJSONを使う")
    args = ap.parse_args()
    date = args.date or today()

    if args.command == "prepare":
        prepare(date, args.content_json)
    elif args.command == "post":
        if not args.slot:
            ap.error("--slot が必要です")
        post_slot(date, args.slot)
    elif args.command == "note":
        post_note(date)
    else:
        auto(date)

    if _failures:
        print(f"失敗: {', '.join(_failures)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
