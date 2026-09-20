"""
news_state.py

Tracks:
1. Which article URLs were already posted.
2. How many posts were published today.
3. Which crypto tickers were already posted today.

Rules:
- Same article URL cannot be posted twice.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- Daily reset follows Bangladesh time (Asia/Dhaka).
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
    """
    Load saved bot state.

    State contains:
    - date
    - daily post count
    - previously posted article URLs
    - today's posted crypto tickers
    """

    if not os.path.exists(cfg.NEWS_STATE_FILE):

        return {
            "date": _today_str(),
            "count": 0,
            "seen_urls": [],
            "posted_tickers": [],
        }

    try:

        with open(
            cfg.NEWS_STATE_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            state = json.load(f)

    except Exception as err:

        print(
            f"[news_state] failed to load state: "
            f"{err}"
        )

        return {
            "date": _today_str(),
            "count": 0,
            "seen_urls": [],
            "posted_tickers": [],
        }

    today = _today_str()

    # ---------------------------------------------------------
    # New Bangladesh day
    # ---------------------------------------------------------

    if state.get("date") != today:

        state = {
            "date": today,
            "count": 0,
            "seen_urls": state.get(
                "seen_urls",
                [],
            ),
            "posted_tickers": [],
        }

    # ---------------------------------------------------------
    # Compatibility / cleanup
    # ---------------------------------------------------------

    state["date"] = today

    try:

        state["count"] = int(
            state.get(
                "count",
                0,
            )
        )

    except (TypeError, ValueError):

        state["count"] = 0

    state["seen_urls"] = list(
        state.get(
            "seen_urls",
            [],
        )
    )

    # Normalize today's ticker list
    state["posted_tickers"] = list(
        dict.fromkeys(
            str(t).upper().strip()
            for t in state.get(
                "posted_tickers",
                [],
            )
            if t
        )
    )

    return state


def save_state(state: dict) -> None:
    """
    Save state safely.

    Writes to a temporary file first and then replaces
    the original state file.
    """

    state["date"] = _today_str()

    temp_file = (
        f"{cfg.NEWS_STATE_FILE}.tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            state,
            f,
            indent=2,
            ensure_ascii=False,
        )

        f.write("\n")

    os.replace(
        temp_file,
        cfg.NEWS_STATE_FILE,
    )


def can_post_more_today(
    state: dict,
) -> bool:
    """
    Check whether today's daily post limit
    has been reached.
    """

    return (
        state.get(
            "count",
            0,
        )
        < cfg.NEWS_MAX_POSTS_PER_DAY
    )


def already_covered(
    state: dict,
    url: str,
) -> bool:
    """
    Check whether this article URL was
    already posted.
    """

    if not url:
        return True

    return url in state.get(
        "seen_urls",
        [],
    )


def ticker_posted_today(
    state: dict,
    ticker: str,
) -> bool:
    """
    Check whether this crypto ticker
    was already posted today.
    """

    if not ticker:
        return True

    ticker = str(
        ticker
    ).upper().strip()

    posted_tickers = {
        str(t).upper().strip()
        for t in state.get(
            "posted_tickers",
            [],
        )
        if t
    }

    return ticker in posted_tickers


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

    # ---------------------------------------------------------
    # Make sure state belongs to today's Bangladesh date
    # ---------------------------------------------------------

    today = _today_str()

    if state.get("date") != today:

        state["date"] = today
        state["count"] = 0
        state["posted_tickers"] = []

    # ---------------------------------------------------------
    # Daily post count
    # ---------------------------------------------------------

    state["count"] = (
        int(
            state.get(
                "count",
                0,
            )
        )
        + 1
    )

    # ---------------------------------------------------------
    # Save article URL
    # ---------------------------------------------------------

    seen = list(
        state.get(
            "seen_urls",
            [],
        )
    )

    if url and url not in seen:

        seen.append(url)

    history_size = max(
        1,
        int(
            cfg.NEWS_SEEN_HISTORY_SIZE
        ),
    )

    state["seen_urls"] = seen[
        -history_size:
    ]

    # ---------------------------------------------------------
    # Save today's crypto ticker
    # ---------------------------------------------------------

    if ticker:

        ticker = str(
            ticker
        ).upper().strip()

        posted_tickers = [
            str(t).upper().strip()
            for t in state.get(
                "posted_tickers",
                [],
            )
            if t
        ]

        if ticker not in posted_tickers:

            posted_tickers.append(
                ticker
            )

        state["posted_tickers"] = list(
            dict.fromkeys(
                posted_tickers
            )
        )

    return state
