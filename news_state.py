"""
news_state.py

Tracks:
1. Which article URLs were already posted.
2. How many posts were published today.
3. Which crypto tickers were already posted today.

Rule:
The same crypto ticker can only be posted ONCE per day.
The daily reset follows Bangladesh time (Asia/Dhaka).
"""

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import config as cfg


DHAKA_TZ = ZoneInfo("Asia/Dhaka")


def _today_str() -> str:
    """Return today's date in Bangladesh time."""
    return datetime.now(DHAKA_TZ).date().isoformat()


def load_state() -> dict:
    if not os.path.exists(cfg.NEWS_STATE_FILE):
        return {
            "date": _today_str(),
            "count": 0,
            "seen_urls": [],
            "posted_tickers": [],
        }

    with open(cfg.NEWS_STATE_FILE, "r") as f:
        state = json.load(f)

    # New Bangladesh day:
    # reset daily post count and ticker list.
    if state.get("date") != _today_str():
        state = {
            "date": _today_str(),
            "count": 0,
            "seen_urls": state.get("seen_urls", []),
            "posted_tickers": [],
        }

    # Compatibility with old state files.
    if "posted_tickers" not in state:
        state["posted_tickers"] = []

    return state


def save_state(state: dict) -> None:
    with open(cfg.NEWS_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def can_post_more_today(state: dict) -> bool:
    return state.get("count", 0) < cfg.NEWS_MAX_POSTS_PER_DAY


def already_covered(state: dict, url: str) -> bool:
    return url in state.get("seen_urls", [])


def ticker_posted_today(
    state: dict,
    ticker: str,
) -> bool:
    """
    Check whether this crypto ticker was already posted today.
    """

    if not ticker:
        return True

    ticker = ticker.upper()

    return ticker in {
        t.upper()
        for t in state.get("posted_tickers", [])
    }


def record_post(
    state: dict,
    url: str,
    ticker: str | None = None,
) -> dict:
    """
    Record a successful post.

    Saves:
    - article URL
    - daily post count
    - crypto ticker posted today
    """

    state["count"] = state.get("count", 0) + 1

    # ---------------------------------------------------------
    # Save article URL
    # ---------------------------------------------------------

    seen = state.get("seen_urls", [])

    if url:
        seen.append(url)

    state["seen_urls"] = seen[
        -cfg.NEWS_SEEN_HISTORY_SIZE:
    ]

    # ---------------------------------------------------------
    # Save today's crypto ticker
    # ---------------------------------------------------------

    if ticker:
        ticker = ticker.upper()

        posted_tickers = state.get(
            "posted_tickers",
            [],
        )

        if ticker not in posted_tickers:
            posted_tickers.append(ticker)

        state["posted_tickers"] = posted_tickers

    return state
