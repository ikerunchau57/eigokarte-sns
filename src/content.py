"""Claude API でその日の全SNS向けコンテンツを一括生成する。"""
from __future__ import annotations

import json
from typing import List

import anthropic
from pydantic import BaseModel, Field

MODEL = "claude-opus-5-5"


class Slide(BaseModel):
    heading: str = Field(description="スライド見出し（全角16文字以内）")
    body: str = Field(description="スライド本文（全角60文字以内、改行は\\nで最大3行）")


class DailyContent(BaseModel):
    topic: str
    x_posts: List[str] = Field(description="X用投稿3本（朝・昼・夜）。各全角135文字以内、ハッシュタグ含む")
    threads_posts: List[str] = Field(description="Threads用投稿3本（朝・昼・夜）。各400文字以内")
    note_title: str = Field(description="note記事タイトル（32文字以内）")
    note_body_markdown: str = Field(description="note記事本文。Markdown、2500〜4000字、見出し(##)付き")
    instagram_caption: str = Field(description="Instagramキャプション。1500文字以内、ハッシュタグは末尾")
    slides: List[Slide] = Field(description="Instagramカルーセル兼動画用スライド5〜7枚。1枚目は表紙")
    thumbnail_title: str = Field(description="サムネイル用の大見出し（全角20文字以内）")
    thumbnail_subtitle: str = Field(description="サムネイル用の小見出し（全角24文字以内）")
    self_check: str = Field(description="事実の誤りや根拠のない数字がないかの自己点検メモ（投稿されない）")


SYSTEM = """あなたは「{name}」のSNS編集者です。医学部受験・共通テスト英語の受験生に本当に役立つ情報を発信し、{name}を自然に知ってもらうことが目的です。

# {name}について
{description}
キャッチコピー: {tagline}
URL: {url}
読者: {audience}
文体: {tone}

# 守ること
- 日付・配点・倍率・統計などの具体的な数字や制度は、下の「確認済みの事実」にあるものだけ使う。ない場合は数字を出さずに書く。
- 特定の大学の入試内容を断定しない（「〜大学では〜が出る」と書かない）。一般的な傾向として書く。
- 「速報値」とある日程を使うときは、必ず「最新情報は各大学の募集要項で確認してください」と添える。
- 合格保証・誇大表現・他社批判をしない。
- 宣伝は控えめにし、各媒体で1回だけ{name}に自然に触れる。Xの投稿にはURLを入れない（リンクは別途付与される）。
- 英語の例文・単語は正確に。訳もつける。
- 朝・昼・夜の3本は同じテーマでも切り口を変える（朝: 今日やること、昼: 具体例・ミニ問題、夜: 振り返り・保存したくなるまとめ）。

# 紹介してよいページ（今日のおすすめ: {promo}）
{links}
note記事の最後と、Instagramキャプションでは「今日のおすすめ」に自然に触れる。URLはnote本文にのみ書く。

# 確認済みの事実
{facts}
"""


def build_system(brand: dict, facts: list[str], promo: dict) -> str:
    return SYSTEM.format(
        promo=f"{promo['title']} {promo['url']}",
        links="\n".join(f"- {l['title']}: {l['url']}" for l in brand.get("promo_links", [])),
        name=brand["name"],
        description=brand["description"].strip(),
        tagline=brand["tagline"],
        url=brand["url"],
        audience=brand["audience"],
        tone=brand["tone"],
        facts="\n".join(f"- {f}" for f in facts) or "- （なし）",
    )


def generate(brand: dict, facts: list[str], category: str, topic: str, date_label: str, promo: dict) -> DailyContent:
    client = anthropic.Anthropic()
    hashtags = brand["hashtags"]
    prompt = (
        f"今日（{date_label}）のテーマ: 【{category}】{topic}\n\n"
        f"Xのハッシュタグ候補: {' '.join(hashtags['x'])}\n"
        f"Instagramのハッシュタグ: {' '.join(hashtags['instagram'])}\n\n"
        "このテーマで、X・Threads・note・Instagram（カルーセルと縦型動画）用のコンテンツを一式作ってください。"
    )
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=build_system(brand, facts, promo),
        messages=[{"role": "user", "content": prompt}],
        output_format=DailyContent,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"生成が拒否されました: {response.stop_details}")
    content = response.parsed_output
    _validate(content)
    return content


def _validate(c: DailyContent) -> None:
    problems = []
    if len(c.x_posts) < 3:
        problems.append("X投稿が3本ありません")
    if len(c.threads_posts) < 3:
        problems.append("Threads投稿が3本ありません")
    for i, p in enumerate(c.x_posts):
        if _x_weight(p) > 280:
            problems.append(f"X投稿{i + 1}が長すぎます")
    if len(c.slides) < 3:
        problems.append("スライドが少なすぎます")
    if problems:
        raise ValueError(" / ".join(problems))


def _x_weight(text: str) -> int:
    """Xの文字数カウント（全角=2、半角=1の簡易版）。"""
    return sum(1 if ord(ch) < 0x1100 else 2 for ch in text)


def load(path) -> DailyContent:
    return DailyContent.model_validate(json.loads(path.read_text(encoding="utf-8")))
