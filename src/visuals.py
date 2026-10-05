"""サムネイル・Instagramカルーセル・動画フレームを Pillow で描画する。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
]


def _font_path() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise FileNotFoundError("日本語フォントが見つかりません（fonts-noto-cjk を入れてください）")


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_font_path(), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if draw.textlength(line + ch, font=font) > max_width and line:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
    return lines


def _fit(draw, text, max_width, max_height, start, min_size=28, spacing=1.35):
    size = start
    while size > min_size:
        font = _font(size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) * size * spacing <= max_height:
            return font, lines, size
        size -= 4
    font = _font(min_size)
    return font, _wrap(draw, text, font, max_width), min_size


def _draw_lines(draw, lines, font, size, x, y, fill, spacing=1.35, center_width=None):
    for line in lines:
        if center_width:
            w = draw.textlength(line, font=font)
            draw.text((x + (center_width - w) / 2, y), line, font=font, fill=fill)
        else:
            draw.text((x, y), line, font=font, fill=fill)
        y += int(size * spacing)
    return y


def _frame(size, colors, brand_name, label):
    W, H = size
    img = Image.new("RGB", size, colors["background"])
    d = ImageDraw.Draw(img)
    band = int(H * 0.09)
    d.rectangle([0, 0, W, band], fill=colors["primary"])
    # カルテ風の赤い縦線
    d.rectangle([int(W * 0.06), band, int(W * 0.06) + 6, H], fill=colors["accent"])
    f = _font(int(band * 0.42))
    d.text((int(W * 0.06), int(band * 0.28)), brand_name, font=f, fill="white")
    if label:
        lw = d.textlength(label, font=f)
        d.text((W - int(W * 0.06) - lw, int(band * 0.28)), label, font=f, fill="white")
    return img, d, band


def render_cover(path: Path, size, colors, brand_name, title, subtitle, label="") -> Path:
    W, H = size
    img, d, band = _frame(size, colors, brand_name, label)
    left = int(W * 0.12)
    width = int(W * 0.80)
    font, lines, fs = _fit(d, title, width, int(H * 0.45), start=int(W * 0.095))
    total = len(lines) * int(fs * 1.35)
    y = band + (H - band - total) // 2 - int(H * 0.06)
    y = _draw_lines(d, lines, font, fs, left, y, colors["text"])
    d.rectangle([left, y + 10, left + int(width * 0.25), y + 18], fill=colors["accent"])
    sfont, slines, ss = _fit(d, subtitle, width, int(H * 0.18), start=int(W * 0.045))
    _draw_lines(d, slines, sfont, ss, left, y + 40, colors["primary"])
    img.save(path, quality=92)
    return path


def render_slide(path: Path, size, colors, brand_name, heading, body, page_label) -> Path:
    W, H = size
    img, d, band = _frame(size, colors, brand_name, page_label)
    left = int(W * 0.12)
    width = int(W * 0.80)
    hfont, hlines, hs = _fit(d, heading, width, int(H * 0.22), start=int(W * 0.08))
    bfont, blines, bs = _fit(d, body, width, int(H * 0.45), start=int(W * 0.062))
    block = len(hlines) * int(hs * 1.35) + 50 + len(blines) * int(bs * 1.6)
    footer = int(H * 0.08)
    y = band + (H - band - footer - block) // 2
    y = _draw_lines(d, hlines, hfont, hs, left, y, colors["primary"])
    d.rectangle([left, y + 8, left + int(width * 0.18), y + 14], fill=colors["accent"])
    _draw_lines(d, blines, bfont, bs, left, y + 50, colors["text"], spacing=1.6)
    # 下部の帯: 保存を促す一言
    d.rectangle([0, H - footer, W, H], fill=colors["primary"])
    ffont = _font(int(footer * 0.36))
    note = "保存して見返そう"
    d.text(((W - d.textlength(note, font=ffont)) / 2, H - footer + int(footer * 0.3)), note, font=ffont, fill="white")
    img.save(path, quality=92)
    return path


def render_all(content, brand: dict, out_dir: Path) -> dict:
    """1日分の画像をすべて描画し、パスを返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    colors = brand["colors"]
    name = brand["name"]
    result = {
        "note_header": render_cover(out_dir / "note_header.jpg", (1280, 670), colors, name,
                                    content.thumbnail_title, content.thumbnail_subtitle),
        "x_image": render_cover(out_dir / "x_image.jpg", (1200, 675), colors, name,
                                content.thumbnail_title, content.thumbnail_subtitle),
        "carousel": [],
        "video_frames": [],
    }
    n = len(content.slides)
    for i, s in enumerate(content.slides):
        label = f"{i + 1}/{n}"
        sq = out_dir / f"carousel_{i + 1:02d}.jpg"
        vt = out_dir / f"frame_{i + 1:02d}.jpg"
        if i == 0:
            render_cover(sq, (1080, 1350), colors, name, s.heading, s.body, label)
            render_cover(vt, (1080, 1920), colors, name, s.heading, s.body, "")
        else:
            render_slide(sq, (1080, 1350), colors, name, s.heading, s.body, label)
            render_slide(vt, (1080, 1920), colors, name, s.heading, s.body, label)
        result["carousel"].append(sq)
        result["video_frames"].append(vt)
    return result
