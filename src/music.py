"""著作権フリーのBGMをその場で合成する（毎日キーとコード進行を変える）。

外部のAI作曲サービスに頼らないので、権利・費用・API停止のリスクがありません。
assets/bgm/ に自前の音源（.mp3/.wav）を置けば、そちらを優先して使います。
"""
from __future__ import annotations

import random
import wave
from pathlib import Path

import numpy as np

SR = 44100
PROGRESSIONS = [
    [0, 5, 3, 4],   # I - vi - IV - V
    [0, 4, 5, 3],   # I - V - vi - IV
    [3, 4, 0, 5],   # IV - V - I - vi
    [5, 3, 0, 4],   # vi - IV - I - V
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]


def _chord(root_midi: int, degree: int) -> list[int]:
    notes = []
    for step in (0, 2, 4):
        idx = degree + step
        octave, pos = divmod(idx, 7)
        notes.append(root_midi + MAJOR[pos] + 12 * octave)
    return notes


def _tone(freq: float, dur: float, amp: float) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    # 柔らかいパッド: 基音+倍音を少し、ゆっくりした立ち上がり
    w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t) + 0.1 * np.sin(2 * np.pi * freq * 3 * t)
    env = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.6)
    return amp * w * env


def _midi_to_hz(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def synthesize(path: Path, seconds: float, seed: int) -> Path:
    rng = random.Random(seed)
    root = 57 + rng.randint(0, 7)          # A3〜E4 のどれか
    prog = rng.choice(PROGRESSIONS)
    bar = rng.choice([2.4, 2.6, 2.8])      # 1小節の長さ（ゆったり）
    total = np.zeros(int(SR * (seconds + 1)))
    pos = 0.0
    i = 0
    while pos < seconds:
        deg = prog[i % len(prog)]
        start = int(pos * SR)
        for n in _chord(root, deg):
            seg = _tone(_midi_to_hz(n), bar, 0.10)
            total[start:start + len(seg)] += seg[: len(total) - start]
        bass = _tone(_midi_to_hz(root - 12 + MAJOR[deg % 7]), bar, 0.12)
        total[start:start + len(bass)] += bass[: len(total) - start]
        # アルペジオ（8分音符）
        step = bar / 8
        for k in range(8):
            n = rng.choice(_chord(root + 12, deg))
            seg = _tone(_midi_to_hz(n), step * 1.5, 0.05)
            s = start + int(k * step * SR)
            total[s:s + len(seg)] += seg[: max(0, len(total) - s)]
        pos += bar
        i += 1
    total = total[: int(SR * seconds)]
    fade = int(SR * 1.5)
    total[-fade:] *= np.linspace(1, 0, fade)
    total /= max(1e-6, np.abs(total).max()) / 0.6
    pcm = (total * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())
    return path


def pick_or_make(out_dir: Path, seconds: float, seed: int, assets_dir: Path) -> Path:
    bgm_dir = assets_dir / "bgm"
    own = sorted(p for p in bgm_dir.glob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a"}) if bgm_dir.exists() else []
    if own:
        return own[seed % len(own)]
    return synthesize(out_dir / "bgm.wav", seconds, seed)
