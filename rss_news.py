"""
rss_news.py

Fetches crypto news from public RSS feeds.

RSS sources:
1. Cointelegraph
2. CoinDesk
3. Decrypt
4. Bitcoin Magazine

Rules:
- No API key required.
- Only public RSS feed data is used.
- Does not download or reproduce full articles.
- Returns articles in the same basic format used by news_fetch.py.
- Duplicate URLs are removed.
- Feed failures do not stop the bot.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import feedparser
import requests


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

REQUEST_TIMEOUT = (
    10,
    30,
)

MAX_RETRIES = 2

MAX_ARTICLES_PER_FEED = 30

MAX_TOTAL_ARTICLES = 100


RSS_FEEDS = [
    (
        "Cointelegraph",
        "https://cointelegraph.com/rss",
    ),
    (
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ),
    (
        "Decrypt",
        "https://decrypt.co/feed",
    ),
    (
        "Bitcoin Magazine",
        "https://bitcoinmagazine.com/.rss/full/",
    ),
]


# ---------------------------------------------------------
# HTTP session
# ---------------------------------------------------------

_session = requests.Session()

_session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; NewsPostBot/1.0)"
        ),
        "Accept": (
            "application/rss+xml,"
            "application/atom+xml,"
            "application/xml,"
            "text/xml,"
            "*/*"
        ),
        "Connection": "keep-alive",
    }
)


# =========================================================
# Helpers
# =========================================================

def _clean_text(value) -> str:
    """
    Convert RSS field to clean text.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip()


def _get_entry_timestamp(
    entry,
) -> float:
    """
    Convert RSS published/updated time into
    a Unix timestamp.

    Returns 0 when unavailable.
    """

    for field_name in (
        "published_parsed",
        "updated_parsed",
        "created_parsed",
    ):

        parsed_time = getattr(
            entry,
            field_name,
            None,
        )

        if parsed_time:

            try:

                return float(
                    time.mktime(
                        parsed_time
                    )
                )

            except (
                TypeError,
                ValueError,
                OverflowError,
            ):

                pass

    return 0.0


def _get_summary(
    entry,
) -> str:
    """
    Get RSS summary/description.

    RSS feeds generally provide a short excerpt.
    """

    summary = getattr(
        entry,
        "summary",
        "",
    )

    if not summary:

        summary = getattr(
            entry,
            "description",
            "",
        )

    return _clean_text(
        summary
    )


def _get_url(
    entry,
) -> str:
    """
    Get the article URL from an RSS entry.
    """

    link = getattr(
        entry,
        "link",
        "",
    )

    if link:
        return _clean_text(
            link
        )

    links = getattr(
        entry,
        "links",
        [],
    )

    if isinstance(
        links,
        list,
    ):

        for item in links:

            if not isinstance(
                item,
                dict,
            ):
                continue

            href = _clean_text(
                item.get(
                    "href",
                    "",
                )
            )

            if href:

                return href

    return ""


# =========================================================
# Single RSS feed
# =========================================================

def _fetch_single_feed(
    source: str,
    feed_url: str,
) -> list[dict]:
    """
    Fetch and parse one RSS feed.
    """

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        response = None

        try:

            print(
                "[rss_news] requesting "
                f"{source} "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = _session.get(
                feed_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )

            print(
                f"[rss_news] {source} response: "
                f"HTTP {response.status_code}"
            )

            response.raise_for_status()

            # -------------------------------------------------
            # Parse RSS / Atom XML
            # -------------------------------------------------

            parsed = feedparser.parse(
                response.content
            )

            if getattr(
                parsed,
                "bozo",
                False,
            ):

                bozo_exception = getattr(
                    parsed,
                    "bozo_exception",
                    None,
                )

                if bozo_exception:

                    print(
                        f"[rss_news] {source} "
                        f"parser warning: "
                        f"{bozo_exception}"
                    )

            entries = getattr(
                parsed,
                "entries",
                [],
            )

            if not entries:

                print(
                    f"[rss_news] {source} "
                    "returned no entries."
                )

                return []

            articles = []

            for entry in entries[
                :MAX_ARTICLES_PER_FEED
            ]:

                title = _clean_text(
                    getattr(
                        entry,
                        "title",
                        "",
                    )
                )

                url = _get_url(
                    entry
                )

                summary = _get_summary(
                    entry
                )

                if not title:
                    continue

                if not url:
                    continue

                timestamp = (
                    _get_entry_timestamp(
                        entry
                    )
                )

                articles.append(
                    {
                        "category": "crypto",

                        "headline": title,
                        "title": title,

                        "summary": summary,
                        "description": summary,

                        "url": url,

                        # RSS feed image is intentionally
                        # not used by the current bot.
                        "image": "",
                        "image_url": "",

                        "source": source,

                        "datetime": timestamp,

                        "provider": "rss",
                    }
                )

            print(
                f"[rss_news] {source} returned "
                f"{len(articles)} usable article(s)."
            )

            return articles

        except requests.exceptions.Timeout as err:

            print(
                f"[rss_news] {source} timeout "
                f"(attempt {attempt}): {err}"
            )

        except requests.exceptions.ConnectionError as err:

            print(
                f"[rss_news] {source} connection "
                f"error (attempt {attempt}): {err}"
            )

        except requests.exceptions.HTTPError as err:

            status_code = (
                response.status_code
                if response is not None
                else "unknown"
            )

            print(
                f"[rss_news] {source} HTTP error "
                f"{status_code}: {err}"
            )

            # RSS feed is not worth repeatedly retrying
            # normal 4xx errors.
            if status_code not in {
                429,
                500,
                502,
                503,
                504,
            }:

                return []

        except Exception as err:

            print(
                f"[rss_news] {source} failed: "
                f"{err}"
            )

            return []

        finally:

            if response is not None:
                response.close()

        if attempt < MAX_RETRIES:

            delay = attempt * 2

            print(
                f"[rss_news] {source} retrying "
                f"in {delay} second(s)..."
            )

            time.sleep(
                delay
            )

    print(
        f"[rss_news] all {source} attempts failed."
    )

    return []


# =========================================================
# Public RSS function
# =========================================================

def fetch_rss_crypto_news() -> list[dict]:
    """
    Fetch crypto news from all configured RSS feeds.

    Returns:
        A combined list of normalized article dictionaries.

    Feed failures are ignored so another feed can still work.
    """

    all_articles = []

    seen_urls = set()

    print(
        "[rss_news] starting RSS fallback..."
    )

    for source, feed_url in RSS_FEEDS:

        articles = _fetch_single_feed(
            source,
            feed_url,
        )

        for article in articles:

            url = article.get(
                "url",
                "",
            )

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(
                url
            )

            all_articles.append(
                article
            )

            if (
                len(all_articles)
                >= MAX_TOTAL_ARTICLES
            ):

                break

        if (
            len(all_articles)
            >= MAX_TOTAL_ARTICLES
        ):

            break

    # ---------------------------------------------------------
    # Newest articles first
    # ---------------------------------------------------------

    all_articles.sort(
        key=lambda item: float(
            item.get(
                "datetime",
                0,
            )
            or 0
        ),
        reverse=True,
    )

    print(
        "[rss_news] total RSS articles: "
        f"{len(all_articles)}"
    )

    return all_articles
