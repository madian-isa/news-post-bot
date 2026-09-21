"""
news_fetch.py

Multi-source crypto news aggregator:
1. Finnhub (API)
2. CoinMarketCap (API)
3. CoinTelegraph (Free RSS)
4. Decrypt (Free RSS)
5. CryptoPanic (Free Public API)

Features:
- Collects and merges news from all working sources.
- Normalizes all articles into the standard format expected by the bot.
- Uses short-term cache to avoid rate limits.
"""

from __future__ import annotations

import time
import requests
import xml.etree.ElementTree as ET

import config as cfg

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

CACHE_TTL_SECONDS = 10 * 60  # Cache for 10 minutes
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 1

CMC_CONTENT_URL = "https://pro-api.coinmarketcap.com/v1/content/latest"

# ---------------------------------------------------------
# Cache & Session
# ---------------------------------------------------------

_cache = {
    "fetched_at": 0,
    "articles": [],
}

_session = requests.Session()
_session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, application/xml, text/xml",
        "Connection": "keep-alive",
    }
)


# =========================================================
# 1. FINNHUB
# =========================================================

def _fetch_from_finnhub() -> list:
    url = "https://finnhub.io/api/v1/news"
    key = str(getattr(cfg, "FINNHUB_API_KEY", "") or "").strip()
    if not key:
        return []

    params = {"category": "crypto", "token": key}
    try:
        print("[news_fetch] Requesting Finnhub crypto news...")
        res = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200 and isinstance(res.json(), list):
            articles = res.json()
            for art in articles:
                art["provider"] = "finnhub"
            print(f"[news_fetch] Finnhub returned {len(articles)} articles.")
            return articles
    except Exception as err:
        print(f"[news_fetch] Finnhub error: {err}")
    return []


# =========================================================
# 2. COINMARKETCAP
# =========================================================

def _normalize_cmc_article(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    
    url = str(item.get("url") or item.get("article_url") or item.get("source_url") or "").strip()
    title = str(item.get("title") or item.get("headline") or item.get("name") or "").strip()
    
    if not url or not title:
        return None

    summary = str(item.get("description") or item.get("summary") or "").strip()
    image = str(item.get("image_url") or item.get("image") or "").strip()
    source = str(item.get("source") or "CoinMarketCap").strip()
    timestamp = item.get("published_at") or item.get("created_at") or int(time.time())

    return {
        "category": "crypto",
        "headline": title,
        "title": title,
        "summary": summary,
        "description": summary,
        "url": url,
        "image": image,
        "image_url": image,
        "source": source,
        "datetime": timestamp,
        "provider": "coinmarketcap",
    }

def _fetch_from_coinmarketcap() -> list:
    key = str(getattr(cfg, "CMC_API_KEY", "") or "").strip()
    if not key:
        return []

    headers = {"X-CMC_PRO_API_KEY": key, "Accept": "application/json"}
    params = {"start": 1, "limit": 50}

    try:
        print("[news_fetch] Requesting CoinMarketCap news...")
        res = _session.get(CMC_CONTENT_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            payload = res.json()
            data = payload.get("data", [])
            items = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            
            articles = []
            for item in items:
                norm = _normalize_cmc_article(item)
                if norm:
                    articles.append(norm)
            print(f"[news_fetch] CoinMarketCap returned {len(articles)} articles.")
            return articles
    except Exception as err:
        print(f"[news_fetch] CoinMarketCap error: {err}")
    return []


# =========================================================
# 3. COINTELEGRAPH (FREE RSS)
# =========================================================

def _fetch_from_cointelegraph() -> list:
    url = "https://cointelegraph.com/rss"
    try:
        print("[news_fetch] Requesting CoinTelegraph RSS...")
        res = _session.get(url, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            articles = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "").strip()
                summary = item.findtext("description", "").strip()
                
                if title and link:
                    articles.append({
                        "category": "crypto",
                        "headline": title,
                        "title": title,
                        "summary": summary,
                        "description": summary,
                        "url": link,
                        "image": "",
                        "source": "CoinTelegraph",
                        "datetime": int(time.time()),
                        "provider": "cointelegraph",
                    })
            print(f"[news_fetch] CoinTelegraph returned {len(articles)} articles.")
            return articles
    except Exception as err:
        print(f"[news_fetch] CoinTelegraph RSS error: {err}")
    return []


# =========================================================
# 4. DECRYPT (FREE RSS)
# =========================================================

def _fetch_from_decrypt() -> list:
    url = "https://decrypt.co/feed"
    try:
        print("[news_fetch] Requesting Decrypt RSS...")
        res = _session.get(url, timeout=REQUEST_TIMEOUT)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            articles = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                summary = item.findtext("description", "").strip()
                
                if title and link:
                    articles.append({
                        "category": "crypto",
                        "headline": title,
                        "title": title,
                        "summary": summary,
                        "description": summary,
                        "url": link,
                        "image": "",
                        "source": "Decrypt",
                        "datetime": int(time.time()),
                        "provider": "decrypt",
                    })
            print(f"[news_fetch] Decrypt returned {len(articles)} articles.")
            return articles
    except Exception as err:
        print(f"[news_fetch] Decrypt RSS error: {err}")
    return []


# =========================================================
# MAIN AGGREGATOR FUNCTION
# =========================================================

def fetch_crypto_news() -> list:
    """
    Fetches news from ALL available sources, merges them,
    and removes duplicate URLs to ensure maximum coverage.
    """
    now = time.time()

    # Check valid cache
    if _cache["articles"] and (now - _cache["fetched_at"] < CACHE_TTL_SECONDS):
        print(f"[news_fetch] Using cached articles: {len(_cache['articles'])}")
        return _cache["articles"]

    combined_articles = []
    seen_urls = set()

    # Helper function to append unique items
    def _add_articles(source_articles):
        for art in source_articles:
            url = art.get("url", "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                combined_articles.append(art)

    # 1. Fetch from Finnhub
    _add_articles(_fetch_from_finnhub())

    # 2. Fetch from CoinMarketCap
    _add_articles(_fetch_from_coinmarketcap())

    # 3. Fetch from CoinTelegraph
    _add_articles(_fetch_from_cointelegraph())

    # 4. Fetch from Decrypt
    _add_articles(_fetch_from_decrypt())

    if combined_articles:
        _cache["fetched_at"] = now
        _cache["articles"] = combined_articles
        print(f"[news_fetch] Total aggregated unique articles: {len(combined_articles)}")
        return combined_articles

    # Fallback to old cache if networks fail
    if _cache["articles"]:
        print(f"[news_fetch] Network failed, falling back to previous cache ({len(_cache['articles'])}).")
        return _cache["articles"]

    print("[news_fetch] No news available from any source.")
    return []
