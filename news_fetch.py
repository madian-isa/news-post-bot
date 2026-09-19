"""
news_fetch.py

Pulls recent crypto news from Finnhub, cached for 15 minutes so repeated
calls within one run don't hit the API more than needed.
"""

import time

import requests

import config as cfg


_CACHE_TTL_SECONDS = 15 * 60
_cache = {"fetched_at": 0, "articles": []}


def fetch_crypto_news() -> list:
    now = time.time()

    if (
        now - _cache["fetched_at"] < _CACHE_TTL_SECONDS
        and _cache["articles"]
    ):
        return _cache["articles"]

    try:
        res = requests.get(
            "https://finnhub.io/api/v1/news",
            params={
                "category": "crypto",
                "token": cfg.FINNHUB_API_KEY,
            },
            timeout=10,
        )

        res.raise_for_status()
        articles = res.json() or []

    except requests.RequestException:
        articles = []

    _cache["fetched_at"] = now
    _cache["articles"] = articles

    return articles
