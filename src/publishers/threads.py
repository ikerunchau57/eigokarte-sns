"""Threads API（Meta公式・無料）で投稿する。"""
from __future__ import annotations

import time

import requests

from .common import check, dry_run, env, wait_for_url

BASE = "https://graph.threads.net/v1.0"


def post(text: str, image_url: str | None = None) -> str:
    if dry_run():
        print(f"[DRY_RUN][Threads] {text} {image_url or ''}")
        return "dry-run"
    user_id = env("THREADS_USER_ID")
    token = env("THREADS_ACCESS_TOKEN")
    params = {"text": text, "access_token": token}
    if image_url:
        wait_for_url(image_url)
        params.update(media_type="IMAGE", image_url=image_url)
    else:
        params["media_type"] = "TEXT"
    container = check(requests.post(f"{BASE}/{user_id}/threads", params=params, timeout=60), "Threadsコンテナ作成")
    # Meta推奨: 公開前に少し待つ
    time.sleep(30)
    published = check(
        requests.post(f"{BASE}/{user_id}/threads_publish",
                      params={"creation_id": container["id"], "access_token": token}, timeout=60),
        "Threads公開",
    )
    return published["id"]


def refresh_token(token: str) -> str:
    """長期トークン（60日）を延長する。週1回の更新ワークフローから呼ぶ。"""
    data = check(requests.get("https://graph.threads.net/refresh_access_token",
                              params={"grant_type": "th_refresh_token", "access_token": token}, timeout=30),
                 "Threadsトークン更新")
    return data["access_token"]
