"""note への投稿（ブラウザ自動操作）。

注意: note には公式の投稿APIがありません。ここではブラウザ（Playwright）でログインして
エディタを操作します。note側の画面変更で動かなくなることがあり、規約上のリスクもあるため、
NOTE_MODE で動作を選べるようにしています。
  NOTE_MODE=publish … 自動で公開まで行う
  NOTE_MODE=draft   … 下書き保存まで（公開ボタンだけ人が押す）
  NOTE_MODE=off     … 何もしない（記事は public/ に Markdown で残る）
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import markdown

from .common import PublishError, dry_run, env


def post(title: str, body_markdown: str, shots_dir: Path) -> str:
    mode = os.environ.get("NOTE_MODE", "draft").lower()
    if mode == "off":
        print("[note] NOTE_MODE=off のためスキップ")
        return "skipped"
    if dry_run():
        print(f"[DRY_RUN][note:{mode}] {title} ({len(body_markdown)}字)")
        return "dry-run"

    from playwright.sync_api import sync_playwright

    html = markdown.markdown(body_markdown)
    shots_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ja-JP", viewport={"width": 1280, "height": 900})
        try:
            page.goto("https://note.com/login", wait_until="domcontentloaded")
            page.locator("input#email, input[name='login'], input[type='email']").first.fill(env("NOTE_EMAIL"))
            page.locator("input#password, input[type='password']").first.fill(env("NOTE_PASSWORD"))
            page.get_by_role("button", name="ログイン").click()
            page.wait_for_url(lambda u: "login" not in u, timeout=30000)

            page.goto("https://editor.note.com/new", wait_until="networkidle")
            title_box = page.locator("textarea[placeholder*='タイトル']").first
            title_box.fill(title)

            body = page.locator("div.ProseMirror[contenteditable='true']").first
            body.click()
            # HTMLとして貼り付けると見出し・箇条書きが保たれる
            page.evaluate(
                """([html, text]) => {
                    const dt = new DataTransfer();
                    dt.setData('text/html', html);
                    dt.setData('text/plain', text);
                    const ev = new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true});
                    document.querySelector("div.ProseMirror[contenteditable='true']").dispatchEvent(ev);
                }""",
                [html, body_markdown],
            )
            page.wait_for_timeout(2000)

            if mode == "draft":
                page.get_by_role("button", name="下書き保存").click()
                page.wait_for_timeout(3000)
                page.screenshot(path=str(shots_dir / "note_draft.png"))
                return page.url

            page.get_by_role("button", name="公開に進む").click()
            page.wait_for_timeout(3000)
            page.get_by_role("button", name="投稿する").click()
            page.wait_for_timeout(5000)
            page.screenshot(path=str(shots_dir / "note_published.png"))
            return page.url
        except Exception as e:  # 画面変更時に原因を追えるよう必ずスクショを残す
            page.screenshot(path=str(shots_dir / "note_error.png"))
            raise PublishError(f"note投稿に失敗: {e}") from e
        finally:
            browser.close()
