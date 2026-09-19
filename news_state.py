"""
news_state.py

Tracks which article URLs have already been posted about, and how many
news posts have gone out today — in a small JSON file. The GitHub
Actions workflow commits this file back to the repo after each run, so
it persists across scheduled invocations.
"""

import json
import os
from datetime import datetime, timezone

import config as cfg


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_state() -> dict:
    if not os.path.exists(cfg.NEWS_STATE_FILE):
        return {
            "date": _today_str(),
            "count": 0,
            "seen_urls": [],
        }

    with open(cfg.NEWS_STATE_FILE, "r") as f:
        state = json.load(f)

    if state.get("date") != _today_str():
        state = {
            "date": _today_str(),
            "count": 0,
            "seen_urls": state.get("seen_urls", []),
        }

    return state


def save_state(state: dict) -> None:
    with open(cfg.NEWS_STATE_FILE, "w") as f:
        json.dump(state, f)


def can_post_more_today(state: dict) -> bool:
    return state.get("count", 0) < cfg.NEWS_MAX_POSTS_PER_DAY


def already_covered(state: dict, url: str) -> bool:
    return url in state.get("seen_urls", [])


def record_post(state: dict, url: str) -> dict:
    state["count"] = state.get("count", 0) + 1

    seen = state.get("seen_urls", [])
    seen.append(url)

    state["seen_urls"] = seen[-cfg.NEWS_SEEN_HISTORY_SIZE:]

    return state
