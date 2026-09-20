"""
news_fetch.py

Crypto news fetcher with two primary sources:

1. Finnhub
2. CoinMarketCap

Fallback order:
    Finnhub
       ↓
    CoinMarketCap Content
       ↓
    old cache
       ↓
    empty list

Features:
- Crypto news only.
- Finnhub remains the primary source.
- CoinMarketCap is the second source.
- Retries temporary network failures.
- Keeps article dictionaries intact.
- Normalizes CMC articles into the format expected by the bot.
- Uses a short cache to reduce repeated API requests.
"""

from __future__ import annotations

import time

import requests

import config as cfg


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

CACHE_TTL_SECONDS = 15 * 60

REQUEST_TIMEOUT = (
    10,
    30,
)

MAX_RETRIES = 3

RETRY_DELAY_SECONDS = 2

CMC_CONTENT_URL = (
    "https://pro-api.coinmarketcap.com/v1/content/latest"
)


# ---------------------------------------------------------
# Cache
# ---------------------------------------------------------

_cache = {
    "fetched_at": 0,
    "articles": [],
}


# ---------------------------------------------------------
# Session
# ---------------------------------------------------------

_session = requests.Session()

_session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; NewsPostBot/1.0)"
        ),
        "Accept": "application/json",
        "Connection": "keep-alive",
    }
)


# =========================================================
# FINNHUB
# =========================================================

def _fetch_from_finnhub() -> list:
    """
    Fetch crypto news from Finnhub.

    Finnhub is the primary news source.
    """

    url = (
        "https://finnhub.io/api/v1/news"
    )

    params = {
        "category": "crypto",
        "token": getattr(
            cfg,
            "FINNHUB_API_KEY",
            "",
        ),
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        response = None

        try:

            print(
                "[news_fetch] requesting Finnhub "
                "crypto news "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = _session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            print(
                "[news_fetch] Finnhub response: "
                f"HTTP {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(
                data,
                list,
            ):

                print(
                    "[news_fetch] Finnhub returned "
                    "unexpected data format."
                )

                return []

            print(
                "[news_fetch] Finnhub returned "
                f"{len(data)} article(s)."
            )

            return data

        except requests.exceptions.Timeout as err:

            print(
                "[news_fetch] Finnhub timeout "
                f"(attempt {attempt}): {err}"
            )

        except requests.exceptions.ConnectionError as err:

            print(
                "[news_fetch] Finnhub connection "
                f"error (attempt {attempt}): {err}"
            )

        except requests.exceptions.HTTPError as err:

            status_code = (
                response.status_code
                if response is not None
                else "unknown"
            )

            print(
                "[news_fetch] Finnhub HTTP error "
                f"{status_code} "
                f"(attempt {attempt}): {err}"
            )

            # Do not retry normal 4xx errors.
            # Retry rate limiting.
            if status_code != 429:
                return []

        except ValueError as err:

            print(
                "[news_fetch] Finnhub invalid JSON "
                f"(attempt {attempt}): {err}"
            )

            return []

        except requests.RequestException as err:

            print(
                "[news_fetch] Finnhub request failed "
                f"(attempt {attempt}): {err}"
            )

        except Exception as err:

            print(
                "[news_fetch] Finnhub unexpected error "
                f"(attempt {attempt}): {err}"
            )

            return []

        if attempt < MAX_RETRIES:

            delay = (
                RETRY_DELAY_SECONDS
                * attempt
            )

            print(
                "[news_fetch] Finnhub retrying in "
                f"{delay} second(s)..."
            )

            time.sleep(delay)

    print(
        "[news_fetch] all Finnhub attempts failed."
    )

    return []


# =========================================================
# CMC
# =========================================================

def _normalize_cmc_article(
    item: dict,
) -> dict | None:
    """
    Convert a CoinMarketCap content item into a
    simple article dictionary.

    The bot can then process Finnhub and CMC
    articles through the same pipeline.
    """

    if not isinstance(
        item,
        dict,
    ):
        return None

    # -----------------------------------------------------
    # Try common CMC URL fields
    # -----------------------------------------------------

    article_url = (
        item.get("url")
        or item.get("article_url")
        or item.get("source_url")
        or ""
    )

    article_url = str(
        article_url
        or ""
    ).strip()

    if not article_url:
        return None

    # -----------------------------------------------------
    # Title
    # -----------------------------------------------------

    title = (
        item.get("title")
        or item.get("headline")
        or item.get("name")
        or ""
    )

    title = str(
        title
        or ""
    ).strip()

    if not title:
        return None

    # -----------------------------------------------------
    # Description / summary
    # -----------------------------------------------------

    summary = (
        item.get("description")
        or item.get("summary")
        or item.get("excerpt")
        or ""
    )

    summary = str(
        summary
        or ""
    ).strip()

    # -----------------------------------------------------
    # Image
    #
    # We keep it in the article dictionary for
    # compatibility, although the current bot's
    # image system intentionally uses only the
    # verified crypto logo.
    # -----------------------------------------------------

    image = (
        item.get("image_url")
        or item.get("image")
        or item.get("thumbnail")
        or ""
    )

    image = str(
        image
        or ""
    ).strip()

    # -----------------------------------------------------
    # Source
    # -----------------------------------------------------

    source = (
        item.get("source")
        or item.get("publisher")
        or "CoinMarketCap"
    )

    source = str(
        source
        or "CoinMarketCap"
    ).strip()

    # -----------------------------------------------------
    # Timestamp
    # -----------------------------------------------------

    timestamp = (
        item.get("published_at")
        or item.get("published")
        or item.get("created_at")
        or item.get("updated_at")
        or 0
    )

    # -----------------------------------------------------
    # Return normalized article
    # -----------------------------------------------------

    return {
        "category": "crypto",

        "headline": title,
        "title": title,

        "summary": summary,
        "description": summary,

        "url": article_url,

        "image": image,
        "image_url": image,

        "source": source,

        "datetime": timestamp,

        "provider": "coinmarketcap",
    }


def _fetch_from_coinmarketcap() -> list:
    """
    Fetch latest crypto-related content from
    CoinMarketCap.

    CMC Content API:
        /v1/content/latest

    Requires:
        CMC_API_KEY
    """

    api_key = str(
        getattr(
            cfg,
            "CMC_API_KEY",
            "",
        )
        or ""
    ).strip()

    if not api_key:

        print(
            "[news_fetch] CMC_API_KEY is missing. "
            "Skipping CoinMarketCap."
        )

        return []

    params = {
        "start": 1,
        "limit": 100,
    }

    headers = {
        "X-CMC_PRO_API_KEY": api_key,
        "Accept": "application/json",
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        response = None

        try:

            print(
                "[news_fetch] requesting "
                "CoinMarketCap content "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = _session.get(
                CMC_CONTENT_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            print(
                "[news_fetch] CoinMarketCap response: "
                f"HTTP {response.status_code}"
            )

            response.raise_for_status()

            payload = response.json()

            if not isinstance(
                payload,
                dict,
            ):

                print(
                    "[news_fetch] CoinMarketCap "
                    "returned unexpected data format."
                )

                return []

            data = payload.get(
                "data",
                [],
            )

            if isinstance(
                data,
                dict,
            ):

                # Some CMC endpoints return the
                # content list under a nested key.
                items = (
                    data.get("items")
                    or data.get("content")
                    or data.get("articles")
                    or data.get("results")
                    or []
                )

            elif isinstance(
                data,
                list,
            ):

                items = data

            else:

                items = []

            if not isinstance(
                items,
                list,
            ):

                print(
                    "[news_fetch] CoinMarketCap "
                    "content list is invalid."
                )

                return []

            articles = []

            for item in items:

                article = (
                    _normalize_cmc_article(
                        item
                    )
                )

                if article:

                    articles.append(
                        article
                    )

            print(
                "[news_fetch] CoinMarketCap "
                f"returned {len(articles)} "
                "usable article(s)."
            )

            return articles

        except requests.exceptions.Timeout as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"timeout (attempt {attempt}): {err}"
            )

        except requests.exceptions.ConnectionError as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"connection error "
                f"(attempt {attempt}): {err}"
            )

        except requests.exceptions.HTTPError as err:

            status_code = (
                response.status_code
                if response is not None
                else "unknown"
            )

            print(
                "[news_fetch] CoinMarketCap "
                f"HTTP error {status_code} "
                f"(attempt {attempt}): {err}"
            )

            # Do not retry normal authentication,
            # permission, or bad-request errors.
            if status_code not in {
                429,
                500,
                502,
                503,
                504,
            }:

                return []

        except ValueError as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"invalid JSON "
                f"(attempt {attempt}): {err}"
            )

            return []

        except requests.RequestException as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"request failed "
                f"(attempt {attempt}): {err}"
            )

        except Exception as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"unexpected error "
                f"(attempt {attempt}): {err}"
            )

            return []

        if attempt < MAX_RETRIES:

            delay = (
                RETRY_DELAY_SECONDS
                * attempt
            )

            print(
                "[news_fetch] CoinMarketCap "
                f"retrying in {delay} second(s)..."
            )

            time.sleep(delay)

    print(
        "[news_fetch] all CoinMarketCap "
        "attempts failed."
    )

    return []


# =========================================================
# MAIN NEWS FUNCTION
# =========================================================

def fetch_crypto_news() -> list:
    """
    Fetch recent crypto news.

    Priority:

        1. Cache
        2. Finnhub
        3. CoinMarketCap
        4. Previous cache
        5. Empty list
    """

    now = time.time()

    # -----------------------------------------------------
    # Fresh cache
    # -----------------------------------------------------

    if (
        _cache["articles"]
        and (
            now - _cache["fetched_at"]
            < CACHE_TTL_SECONDS
        )
    ):

        print(
            "[news_fetch] using cached articles: "
            f"{len(_cache['articles'])}"
        )

        return _cache["articles"]

    # =====================================================
    # SOURCE 1 — FINNHUB
    # =====================================================

    finnhub_key = str(
        getattr(
            cfg,
            "FINNHUB_API_KEY",
            "",
        )
        or ""
    ).strip()

    if finnhub_key:

        finnhub_articles = (
            _fetch_from_finnhub()
        )

        if finnhub_articles:

            _cache["fetched_at"] = now

            _cache["articles"] = (
                finnhub_articles
            )

            print(
                "[news_fetch] using Finnhub as "
                "primary source: "
                f"{len(finnhub_articles)} article(s)."
            )

            return finnhub_articles

        print(
            "[news_fetch] Finnhub returned "
            "no usable articles."
        )

    else:

        print(
            "[news_fetch] FINNHUB_API_KEY is "
            "missing. Skipping Finnhub."
        )

    # =====================================================
    # SOURCE 2 — COINMARKETCAP
    # =====================================================

    print(
        "[news_fetch] switching to "
        "CoinMarketCap fallback..."
    )

    cmc_articles = (
        _fetch_from_coinmarketcap()
    )

    if cmc_articles:

        _cache["fetched_at"] = now

        _cache["articles"] = (
            cmc_articles
        )

        print(
            "[news_fetch] using CoinMarketCap "
            "as secondary source: "
            f"{len(cmc_articles)} article(s)."
        )

        return cmc_articles

    print(
        "[news_fetch] CoinMarketCap also "
        "returned no usable articles."
    )

    # =====================================================
    # OLD CACHE FALLBACK
    # =====================================================

    if _cache["articles"]:

        print(
            "[news_fetch] using previous cached "
            "articles: "
            f"{len(_cache['articles'])}"
        )

        return _cache["articles"]

    # =====================================================
    # NOTHING AVAILABLE
    # =====================================================

    _cache["fetched_at"] = now

    print(
        "[news_fetch] no news available from "
        "Finnhub or CoinMarketCap."
    )

    return []
