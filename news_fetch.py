"""
news_fetch.py

Pulls recent crypto news from Finnhub.

Features:
- Crypto news only.
- Retry on temporary connection failures.
- Handles connection reset / timeout errors.
- Keeps Finnhub article dictionaries intact.
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


def _fetch_from_finnhub() -> list:
    """
    Fetch crypto news from Finnhub.

    Retries temporary network failures.
    """

    url = "https://finnhub.io/api/v1/news"

    params = {
        "category": "crypto",
        "token": cfg.FINNHUB_API_KEY,
    }

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        try:

            print(
                "[news_fetch] requesting Finnhub "
                f"crypto news "
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
                "[news_fetch] timeout "
                f"(attempt {attempt}): {err}"
            )

        except requests.exceptions.ConnectionError as err:

            print(
                "[news_fetch] connection error "
                f"(attempt {attempt}): {err}"
            )

        except requests.exceptions.HTTPError as err:

            status_code = (
                response.status_code
                if "response" in locals()
                and response is not None
                else "unknown"
            )

            print(
                "[news_fetch] HTTP error "
                f"{status_code} "
                f"(attempt {attempt}): {err}"
            )

            # 4xx errors normally should not be retried
            # except rate limiting.
            if status_code != 429:
                return []

        except ValueError as err:

            print(
                "[news_fetch] invalid JSON "
                f"(attempt {attempt}): {err}"
            )

            return []

        except requests.RequestException as err:

            print(
                "[news_fetch] request failed "
                f"(attempt {attempt}): {err}"
            )

        except Exception as err:

            print(
                "[news_fetch] unexpected error "
                f"(attempt {attempt}): {err}"
            )

            return []

        # -------------------------------------------------
        # Retry delay
        # -------------------------------------------------

        if attempt < MAX_RETRIES:

            delay = (
                RETRY_DELAY_SECONDS
                * attempt
            )

            print(
                "[news_fetch] retrying in "
                f"{delay} second(s)..."
            )

            time.sleep(delay)

    print(
        "[news_fetch] all Finnhub attempts failed."
    )

    return []


def fetch_crypto_news() -> list:
    """
    Fetch recent crypto news from Finnhub.

    Uses cached articles when the cache is still fresh.

    If the API temporarily fails but an older cache
    exists, the old cached articles are returned.
    """

    now = time.time()

    # ---------------------------------------------------------
    # Cache
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Validate API key
    # ---------------------------------------------------------

    api_key = str(
        getattr(
            cfg,
            "FINNHUB_API_KEY",
            "",
        )
        or ""
    ).strip()

    if not api_key:

        print(
            "[news_fetch] FINNHUB_API_KEY is "
            "missing."
        )

        return _cache["articles"]

    # ---------------------------------------------------------
    # Fetch
    # ---------------------------------------------------------

    articles = _fetch_from_finnhub()

    # ---------------------------------------------------------
    # Successful response
    # ---------------------------------------------------------

    if articles:

        _cache["fetched_at"] = now
        _cache["articles"] = articles

        print(
            "[news_fetch] fetched "
            f"{len(articles)} article(s)."
        )

        return articles

    # ---------------------------------------------------------
    # Temporary failure
    #
    # Keep old cache instead of destroying it.
    # ---------------------------------------------------------

    if _cache["articles"]:

        print(
            "[news_fetch] request returned no "
            "articles. Using previous cache: "
            f"{len(_cache['articles'])}"
        )

        return _cache["articles"]

    # ---------------------------------------------------------
    # Nothing available
    # ---------------------------------------------------------

    _cache["fetched_at"] = now

    print(
        "[news_fetch] fetched 0 article(s)."
    )

    return []
