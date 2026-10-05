"""Instagram API（Instagramログイン方式・無料）でカルーセルとリールを投稿する。
プロアカウント（ビジネス/クリエイター）が必要。
"""
from __future__ import annotations

import os
import time

import requests

from .common import PublishError, check, dry_run, env, wait_for_url

VERSION = os.environ.get("IG_API_VERSION", "v23.0")
BASE = f"https://graph.instagram.com/{VERSION}"


def _create(user_id: str, token: str, **params) -> str:
    params["access_token"] = token
    return check(requests.post(f"{BASE}/{user_id}/media", data=params, timeout=60), "Instagramコンテナ作成")["id"]


def _wait_ready(container_id: str, token: str, timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = check(requests.get(f"{BASE}/{container_id}",
                                  params={"fields": "status_code,status", "access_token": token}, timeout=30),
                     "Instagram状態確認")
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise PublishError(f"Instagramの処理に失敗: {data}")
        time.sleep(10)
    raise PublishError("Instagramの動画処理がタイムアウトしました")


def _publish(user_id: str, token: str, creation_id: str) -> str:
    return check(requests.post(f"{BASE}/{user_id}/media_publish",
                               data={"creation_id": creation_id, "access_token": token}, timeout=60),
                 "Instagram公開")["id"]


def post_carousel(image_urls: list[str], caption: str) -> str:
    if dry_run():
        print(f"[DRY_RUN][Instagram carousel] {len(image_urls)}枚 / {caption[:60]}…")
        return "dry-run"
    user_id, token = env("IG_USER_ID"), env("IG_ACCESS_TOKEN")
    children = []
    for url in image_urls[:10]:
        wait_for_url(url)
        children.append(_create(user_id, token, image_url=url, is_carousel_item="true"))
    for c in children:
        _wait_ready(c, token)
    parent = _create(user_id, token, media_type="CAROUSEL", children=",".join(children), caption=caption)
    _wait_ready(parent, token)
    return _publish(user_id, token, parent)


def post_reel(video_url: str, caption: str, cover_url: str | None = None) -> str:
    if dry_run():
        print(f"[DRY_RUN][Instagram reel] {video_url} / {caption[:60]}…")
        return "dry-run"
    user_id, token = env("IG_USER_ID"), env("IG_ACCESS_TOKEN")
    wait_for_url(video_url)
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
    if cover_url:
        params["cover_url"] = cover_url
    container = _create(user_id, token, **params)
    _wait_ready(container, token)
    return _publish(user_id, token, container)


def refresh_token(token: str) -> str:
    data = check(requests.get("https://graph.instagram.com/refresh_access_token",
                              params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30),
                 "Instagramトークン更新")
    return data["access_token"]
