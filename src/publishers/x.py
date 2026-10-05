"""X (Twitter) API v2 で投稿する。従量課金: リンクなし $0.015/件、リンクあり $0.20/件（2026年時点）。"""
from __future__ import annotations

from requests_oauthlib import OAuth1Session

from .common import check, dry_run, env

ENDPOINT = "https://api.x.com/2/tweets"


def post(text: str) -> str:
    if dry_run():
        print(f"[DRY_RUN][X] {text}")
        return "dry-run"
    session = OAuth1Session(
        env("X_API_KEY"),
        client_secret=env("X_API_SECRET"),
        resource_owner_key=env("X_ACCESS_TOKEN"),
        resource_owner_secret=env("X_ACCESS_TOKEN_SECRET"),
    )
    data = check(session.post(ENDPOINT, json={"text": text}, timeout=30), "X投稿")
    return data["data"]["id"]
