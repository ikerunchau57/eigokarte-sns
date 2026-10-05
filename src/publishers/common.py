from __future__ import annotations

import os
import time

import requests


class PublishError(RuntimeError):
    pass


class NotConfigured(PublishError):
    """認証情報が未登録のSNSはエラーにせずスキップする。"""


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise NotConfigured(f"環境変数 {name} が未設定です")
    return value


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}


def wait_for_url(url: str, timeout: int = 300) -> None:
    """GitHub Pages への反映を待つ（Instagram/Threads は公開URLから画像を取りに来るため）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.head(url, timeout=15, allow_redirects=True)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(10)
    raise PublishError(f"公開URLに到達できません: {url}")


def check(r: requests.Response, what: str) -> dict:
    if r.status_code >= 400:
        raise PublishError(f"{what} 失敗 ({r.status_code}): {r.text[:500]}")
    return r.json() if r.content else {}
