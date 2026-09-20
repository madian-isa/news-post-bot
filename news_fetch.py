"""
news_fetch.py

Crypto news fetcher.

Priority:
    1. Finnhub
    2. CoinMarketCap
    3. cryptocurrency.cv JSON API
    4. cryptocurrency.cv RSS feed
    5. previous cache
    6. empty list

cryptocurrency.cv official endpoints:
    JSON:
        https://cryptocurrency.cv/api/news

    RSS:
        https://cryptocurrency.cv/api/rss

No API key is required for cryptocurrency.cv.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

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

CRYPTOCURRENCY_CV_NEWS_URL = (
    "https://cryptocurrency.cv/api/news"
)

CRYPTOCURRENCY_CV_RSS_URL = (
    "https://cryptocurrency.cv/api/rss"
)


# ---------------------------------------------------------
# Cache
# ---------------------------------------------------------

_cache = {
    "fetched_at": 0,
    "articles": [],
}


# ---------------------------------------------------------
# HTTP Session
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
                f"{status_code}: {err}"
            )

            if status_code != 429:
                return []

        except ValueError as err:

            print(
                "[news_fetch] Finnhub invalid JSON: "
                f"{err}"
            )

            return []

        except requests.RequestException as err:

            print(
                "[news_fetch] Finnhub request failed: "
                f"{err}"
            )

        except Exception as err:

            print(
                "[news_fetch] Finnhub unexpected error: "
                f"{err}"
            )

            return []

        if attempt < MAX_RETRIES:

            time.sleep(
                RETRY_DELAY_SECONDS * attempt
            )

    return []


# =========================================================
# COINMARKETCAP
# =========================================================

def _normalize_cmc_article(
    item: dict,
) -> dict | None:

    if not isinstance(
        item,
        dict,
    ):
        return None

    article_url = (
        item.get("url")
        or item.get("article_url")
        or item.get("source_url")
        or ""
    )

    article_url = str(
        article_url or ""
    ).strip()

    if not article_url:
        return None

    title = (
        item.get("title")
        or item.get("headline")
        or item.get("name")
        or ""
    )

    title = str(
        title or ""
    ).strip()

    if not title:
        return None

    summary = (
        item.get("description")
        or item.get("summary")
        or item.get("excerpt")
        or item.get("subtitle")
        or ""
    )

    summary = str(
        summary or ""
    ).strip()

    image = (
        item.get("image_url")
        or item.get("image")
        or item.get("thumbnail")
        or item.get("cover")
        or ""
    )

    image = str(
        image or ""
    ).strip()

    source = (
        item.get("source")
        or item.get("publisher")
        or item.get("source_name")
        or "CoinMarketCap"
    )

    timestamp = (
        item.get("published_at")
        or item.get("published")
        or item.get("created_at")
        or item.get("updated_at")
        or 0
    )

    return {
        "category": "crypto",

        "headline": title,
        "title": title,

        "summary": summary,
        "description": summary,

        "url": article_url,

        "image": image,
        "image_url": image,

        "source": str(
            source or "CoinMarketCap"
        ).strip(),

        "datetime": timestamp,

        "provider": "coinmarketcap",
    }


def _fetch_from_coinmarketcap() -> list:

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
                return []

            data = payload.get(
                "data",
                [],
            )

            if isinstance(
                data,
                dict,
            ):

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
                return []

            articles = []

            for item in items:

                article = (
                    _normalize_cmc_article(
                        item
                    )
                )

                if article:
                    articles.append(article)

            print(
                "[news_fetch] CoinMarketCap "
                f"returned {len(articles)} "
                "usable article(s)."
            )

            return articles

        except requests.exceptions.HTTPError as err:

            status_code = (
                response.status_code
                if response is not None
                else "unknown"
            )

            print(
                "[news_fetch] CoinMarketCap "
                f"HTTP error {status_code}: {err}"
            )

            # Permanent 4xx → immediately continue
            # to cryptocurrency.cv.
            if status_code not in {
                429,
                500,
                502,
                503,
                504,
            }:

                return []

        except requests.RequestException as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"request failed: {err}"
            )

        except ValueError as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"invalid JSON: {err}"
            )

            return []

        except Exception as err:

            print(
                "[news_fetch] CoinMarketCap "
                f"unexpected error: {err}"
            )

            return []

        if attempt < MAX_RETRIES:

            time.sleep(
                RETRY_DELAY_SECONDS * attempt
            )

    return []


# =========================================================
# CRYPTOCURRENCY.CV JSON API
# =========================================================

def _normalize_cryptocurrency_cv_article(
    item: dict,
) -> dict | None:
    """
    Official cryptocurrency.cv article format:

        title
        link
        description
        pubDate
        source
        timeAgo
    """

    if not isinstance(
        item,
        dict,
    ):
        return None

    article_url = (
        item.get("link")
        or item.get("url")
        or item.get("article_url")
        or item.get("source_url")
        or ""
    )

    article_url = str(
        article_url or ""
    ).strip()

    if not article_url:
        return None

    title = (
        item.get("title")
        or item.get("headline")
        or ""
    )

    title = str(
        title or ""
    ).strip()

    if not title:
        return None

    summary = (
        item.get("description")
        or item.get("summary")
        or item.get("excerpt")
        or ""
    )

    summary = str(
        summary or ""
    ).strip()

    source = (
        item.get("source")
        or "cryptocurrency.cv"
    )

    timestamp = (
        item.get("pubDate")
        or item.get("published_at")
        or item.get("published")
        or item.get("created_at")
        or 0
    )

    return {
        "category": "crypto",

        "headline": title,
        "title": title,

        "summary": summary,
        "description": summary,

        "url": article_url,

        "image": "",
        "image_url": "",

        "source": str(
            source or "cryptocurrency.cv"
        ).strip(),

        "datetime": timestamp,

        "timeAgo": item.get(
            "timeAgo",
            "",
        ),

        "provider": "cryptocurrency.cv",
    }


def _fetch_from_cryptocurrency_cv() -> list:
    """
    Fetch from cryptocurrency.cv JSON API.

    Official endpoint:
        https://cryptocurrency.cv/api/news
    """

    try:

        print(
            "[news_fetch] requesting "
            "cryptocurrency.cv news..."
        )

        response = _session.get(
            CRYPTOCURRENCY_CV_NEWS_URL,
            params={
                "limit": 100,
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        print(
            "[news_fetch] cryptocurrency.cv "
            f"response: HTTP {response.status_code}"
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(
            payload,
            dict,
        ):
            return []

        items = payload.get(
            "articles",
            [],
        )

        if not isinstance(
            items,
            list,
        ):
            return []

        articles = []

        for item in items:

            article = (
                _normalize_cryptocurrency_cv_article(
                    item
                )
            )

            if article:
                articles.append(article)

        print(
            "[news_fetch] cryptocurrency.cv "
            f"returned {len(articles)} "
            "usable article(s)."
        )

        return articles

    except requests.exceptions.HTTPError as err:

        status_code = (
            response.status_code
            if "response" in locals()
            else "unknown"
        )

        print(
            "[news_fetch] cryptocurrency.cv "
            f"JSON HTTP error {status_code}: {err}"
        )

        return []

    except requests.RequestException as err:

        print(
            "[news_fetch] cryptocurrency.cv "
            f"JSON request failed: {err}"
        )

        return []

    except ValueError as err:

        print(
            "[news_fetch] cryptocurrency.cv "
            f"JSON invalid response: {err}"
        )

        return []

    except Exception as err:

        print(
            "[news_fetch] cryptocurrency.cv "
            f"JSON unexpected error: {err}"
        )

        return []


# =========================================================
# CRYPTOCURRENCY.CV RSS
# =========================================================

def _get_xml_text(
    element,
    tag_names: tuple[str, ...],
) -> str:

    for tag_name in tag_names:

        child = element.find(tag_name)

        if child is not None:

            value = (
                child.text
                or ""
            ).strip()

            if value:
                return value

    return ""


def _fetch_from_cryptocurrency_cv_rss() -> list:
    """
    RSS fallback for cryptocurrency.cv.

    Official endpoint:
        https://cryptocurrency.cv/api/rss
    """

    try:

        print(
            "[news_fetch] requesting "
            "cryptocurrency.cv RSS fallback..."
        )

        response = _session.get(
            CRYPTOCURRENCY_CV_RSS_URL,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={
                "Accept": (
                    "application/rss+xml, "
                    "application/xml, text/xml, */*"
                ),
            },
        )

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"response: HTTP {response.status_code}"
        )

        response.raise_for_status()

        root = ET.fromstring(
            response.content
        )

        articles = []

        # Standard RSS:
        # <rss>
        #   <channel>
        #     <item>...</item>
        #   </channel>
        # </rss>

        items = root.findall(
            ".//item"
        )

        # Atom fallback:
        # <entry>...</entry>

        if not items:

            items = root.findall(
                ".//{http://www.w3.org/2005/Atom}entry"
            )

        for item in items:

            title = _get_xml_text(
                item,
                (
                    "title",
                    "{http://www.w3.org/2005/Atom}title",
                ),
            )

            if not title:
                continue

            link = _get_xml_text(
                item,
                (
                    "link",
                    "{http://www.w3.org/2005/Atom}link",
                ),
            )

            # Atom <link href="...">
            if not link:

                atom_link = item.find(
                    "{http://www.w3.org/2005/Atom}link"
                )

                if atom_link is not None:

                    link = str(
                        atom_link.attrib.get(
                            "href",
                            "",
                        )
                    ).strip()

            if not link:
                continue

            description = _get_xml_text(
                item,
                (
                    "description",
                    "summary",
                    "{http://www.w3.org/2005/Atom}summary",
                    "{http://www.w3.org/2005/Atom}content",
                ),
            )

            pub_date = _get_xml_text(
                item,
                (
                    "pubDate",
                    "published",
                    "{http://www.w3.org/2005/Atom}published",
                    "{http://www.w3.org/2005/Atom}updated",
                ),
            )

            source = _get_xml_text(
                item,
                (
                    "source",
                    "author",
                    "{http://www.w3.org/2005/Atom}author",
                ),
            )

            if not source:
                source = "cryptocurrency.cv"

            articles.append(
                {
                    "category": "crypto",

                    "headline": title,
                    "title": title,

                    "summary": description,
                    "description": description,

                    "url": link,

                    "image": "",
                    "image_url": "",

                    "source": source,

                    "datetime": pub_date,

                    "provider": (
                        "cryptocurrency.cv_rss"
                    ),
                }
            )

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"returned {len(articles)} "
            "usable article(s)."
        )

        return articles

    except requests.exceptions.HTTPError as err:

        status_code = (
            response.status_code
            if "response" in locals()
            else "unknown"
        )

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"HTTP error {status_code}: {err}"
        )

        return []

    except requests.RequestException as err:

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"request failed: {err}"
        )

        return []

    except ET.ParseError as err:

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"XML parse error: {err}"
        )

        return []

    except Exception as err:

        print(
            "[news_fetch] cryptocurrency.cv RSS "
            f"unexpected error: {err}"
        )

        return []


# =========================================================
# MAIN
# =========================================================

def fetch_crypto_news() -> list:
    """
    Exact fallback order:

        1. Finnhub
        2. CoinMarketCap
        3. cryptocurrency.cv /api/news
        4. cryptocurrency.cv /api/rss
        5. previous cache
        6. empty list
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

    # -----------------------------------------------------
    # 1. FINNHUB
    # -----------------------------------------------------

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
                "[news_fetch] using Finnhub "
                "as primary source: "
                f"{len(finnhub_articles)} article(s)."
            )

            return finnhub_articles

    else:

        print(
            "[news_fetch] FINNHUB_API_KEY is "
            "missing. Skipping Finnhub."
        )

    # -----------------------------------------------------
    # 2. COINMARKETCAP
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # 3. CRYPTOCURRENCY.CV JSON
    # -----------------------------------------------------

    print(
        "[news_fetch] switching to "
        "cryptocurrency.cv JSON fallback..."
    )

    cv_articles = (
        _fetch_from_cryptocurrency_cv()
    )

    if cv_articles:

        _cache["fetched_at"] = now

        _cache["articles"] = (
            cv_articles
        )

        print(
            "[news_fetch] using cryptocurrency.cv "
            "JSON as third source: "
            f"{len(cv_articles)} article(s)."
        )

        return cv_articles

    print(
        "[news_fetch] cryptocurrency.cv JSON "
        "returned no usable articles."
    )

    # -----------------------------------------------------
    # 4. CRYPTOCURRENCY.CV RSS
    # -----------------------------------------------------

    print(
        "[news_fetch] switching to "
        "cryptocurrency.cv RSS fallback..."
    )

    cv_rss_articles = (
        _fetch_from_cryptocurrency_cv_rss()
    )

    if cv_rss_articles:

        _cache["fetched_at"] = now

        _cache["articles"] = (
            cv_rss_articles
        )

        print(
            "[news_fetch] using cryptocurrency.cv "
            "RSS as fourth source: "
            f"{len(cv_rss_articles)} article(s)."
        )

        return cv_rss_articles

    print(
        "[news_fetch] cryptocurrency.cv RSS "
        "also returned no usable articles."
    )

    # -----------------------------------------------------
    # 5. PREVIOUS CACHE
    # -----------------------------------------------------

    if _cache["articles"]:

        print(
            "[news_fetch] using previous cached "
            "articles: "
            f"{len(_cache['articles'])}"
        )

        return _cache["articles"]

    # -----------------------------------------------------
    # 6. NOTHING AVAILABLE
    # -----------------------------------------------------

    _cache["fetched_at"] = now

    print(
        "[news_fetch] no news available from "
        "Finnhub, CoinMarketCap, cryptocurrency.cv "
        "JSON, or cryptocurrency.cv RSS."
    )

    return []
