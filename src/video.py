"""スライド画像とBGMから縦型ショート動画（Reels / Threads / X 向け）を ffmpeg で作る。"""
from __future__ import annotations

import subprocess
from pathlib import Path

SECONDS_PER_SLIDE = 5.0
FADE = 0.5


def build(frames: list[Path], bgm: Path, out: Path) -> Path:
    n = len(frames)
    total = n * SECONDS_PER_SLIDE - (n - 1) * FADE
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in frames:
        cmd += ["-loop", "1", "-t", str(SECONDS_PER_SLIDE), "-i", str(f)]
    cmd += ["-stream_loop", "-1", "-i", str(bgm)]

    # 各スライドにゆっくりズーム → クロスフェードでつなぐ
    parts = []
    for i in range(n):
        parts.append(
            f"[{i}:v]scale=1188:2112,zoompan=z='min(zoom+0.0006,1.06)':d={int(SECONDS_PER_SLIDE * 30)}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,setsar=1,format=yuv420p[v{i}]"
        )
    last = "v0"
    offset = 0.0
    for i in range(1, n):
        offset += SECONDS_PER_SLIDE - FADE
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.2f}[x{i}]")
        last = f"x{i}"
    parts.append(f"[{n}:a]atrim=0:{total:.2f},afade=t=out:st={total - 1.5:.2f}:d=1.5,volume=0.8[a]")
    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", f"[{last}]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart", "-t", f"{total:.2f}", str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def duration_for(n_slides: int) -> float:
    return n_slides * SECONDS_PER_SLIDE - (n_slides - 1) * FADE
