"""
news_fetch.py

Pulls recent crypto news from Finnhub.

The article's image URL is preserved so the posting system
can attach the original news image later.
"""

import time

import requests

import config as cfg


_CACHE_TTL_SECONDS = 15 * 60

_cache = {
    "fetched_at": 0,
    "articles": [],
}


def fetch_crypto_news() -> list:
    """
    Fetch recent crypto news from Finnhub.

    Important:
    We keep the complete article dictionaries, including
    the Finnhub `image` field.
    """

    now = time.time()

    # ---------------------------------------------------------
    # Cache
    # ---------------------------------------------------------

    if (
        now - _cache["fetched_at"]
        < _CACHE_TTL_SECONDS
        and _cache["articles"]
    ):
        return _cache["articles"]

    try:

        response = requests.get(
            "https://finnhub.io/api/v1/news",
            params={
                "category": "crypto",
                "token": cfg.FINNHUB_API_KEY,
            },
            headers={
                "User-Agent": "NewsPostBot/1.0",
            },
            timeout=15,
        )

        response.raise_for_status()

        articles = response.json() or []

        if not isinstance(
            articles,
            list,
        ):
            articles = []

    except requests.RequestException as err:

        print(
            f"[news_fetch] request failed: {err}"
        )

        articles = []

    except ValueError as err:

        print(
            f"[news_fetch] invalid JSON: {err}"
        )

        articles = []

    _cache["fetched_at"] = now
    _cache["articles"] = articles

    print(
        f"[news_fetch] fetched "
        f"{len(articles)} article(s)."
    )

    return articles
