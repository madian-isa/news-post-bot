"""
news_images.py

Prepares post image for crypto/macro news posts.

Rules:
- Maximum 1 image.
- Priority Order:
    1. Original Article Featured Image (Open Graph og:image)
    2. Serper API Search Image (Fallback if article image fails/missing)
    3. Binance Crypto Logo (Final Backup Fallback)
- Uses existing binance_symbols.py verification for Binance logo fallback.
- Returns [] (text-only) if all image sources fail.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# IMPORTANT:
# binance_symbols.py is in the project root,
# so do NOT use "src.binance_symbols".
from binance_symbols import is_binance_crypto_ticker


TIMEOUT = 20
MAX_IMAGE_SIZE = 10 * 1024 * 1024

BINANCE_LOGO_BASE = "https://bin.bnbstatic.com"


def _get_verified_ticker(ticker: str) -> str | None:
    """
    Verify ticker using the project's existing
    Binance Spot asset verification system.
    """
    if not ticker:
        return None

    ticker = str(ticker).upper().strip().replace("$", "")

    if not ticker:
        return None

    try:
        verified = is_binance_crypto_ticker(ticker)
    except Exception as err:
        print(
            f"[news_images] Binance ticker verification failed for ${ticker}: {err}"
        )
        return None

    if not verified:
        print(
            f"[news_images] ${ticker} is not verified by binance_symbols.py."
        )
        return None

    print(f"[news_images] Binance Spot asset verified: ${ticker}")
    return ticker


def _get_logo_candidates(ticker: str) -> list[str]:
    """
    Return possible Binance-hosted logo URLs.
    """
    ticker = str(ticker).upper().strip().replace("$", "")
    if not ticker:
        return []

    return [
        f"{BINANCE_LOGO_BASE}/static/assets/logos/{ticker}.png",
        f"{BINANCE_LOGO_BASE}/static/assets/logos/{ticker.lower()}.png",
    ]


def _download_image(url: str, prefix: str) -> str | None:
    """
    Download one image and verify its response.
    """
    if not url:
        return None

    response = None
    path = None

    try:
        print(f"[news_images] requesting image: {url}")

        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "image/avif,image/webp,image/apng,image/png,"
                    "image/jpeg,image/jpg,image/gif,image/*,*/*;q=0.8"
                ),
            },
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = (
            response.headers.get("Content-Type", "")
            .lower()
            .split(";")[0]
            .strip()
        )

        allowed_types = {
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/webp",
            "image/gif",
            "image/avif",
        }

        if content_type not in allowed_types:
            print(
                "[news_images] rejected image URL because response is not an image: "
                f"{url} (Content-Type: {content_type or 'unknown'})"
            )
            return None

        extension_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/avif": ".avif",
        }

        extension = extension_map.get(content_type, ".png")

        fd, path = tempfile.mkstemp(
            prefix=f"{prefix}_",
            suffix=extension,
        )
        os.close(fd)

        total = 0
        with open(path, "wb") as file:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)

                if total > MAX_IMAGE_SIZE:
                    raise ValueError("Image is larger than 10 MB.")

                file.write(chunk)

        if total <= 0:
            Path(path).unlink(missing_ok=True)
            return None

        print(f"[news_images] downloaded {total:,} bytes.")
        return path

    except Exception as err:
        if path:
            Path(path).unlink(missing_ok=True)
        print(f"[news_images] image download failed: {url} -> {err}")
        return None

    finally:
        if response is not None:
            response.close()


def _get_article_og_image(article_url: str) -> str | None:
    """
    Extract original featured image (og:image) from article URL.
    """
    if not article_url:
        return None

    try:
        print(f"[news_images] scraping OG image from: {article_url}")
        resp = requests.get(
            article_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            og_image = soup.find("meta", property="og:image") or soup.find(
                "meta", attrs={"name": "twitter:image"}
            )
            if og_image and og_image.get("content"):
                image_url = og_image["content"].strip()
                print(f"[news_images] found article image: {image_url}")
                return image_url
    except Exception as err:
        print(f"[news_images] failed to scrape OG image: {err}")

    return None


def _get_serper_search_image(query: str) -> str | None:
    """
    Search image using Serper API (Google Image Search Fallback).
    """
    serper_key = os.environ.get("SERPER_API_KEY", "").strip()
    if not serper_key or not query:
        return None

    try:
        print(f"[news_images] searching Serper API for image: '{query}'")
        url = "https://google.serper.dev/images"
        payload = {"q": query, "gl": "us", "hl": "en", "num": 1}
        headers = {
            "X-API-KEY": serper_key,
            "Content-Type": "application/json",
        }
        resp = requests.post(
            url, json=payload, headers=headers, timeout=TIMEOUT
        )
        if resp.status_code == 200:
            data = resp.json()
            images = data.get("images", [])
            if images and isinstance(images, list):
                img_url = images[0].get("imageUrl")
                if img_url:
                    print(f"[news_images] Serper image found: {img_url}")
                    return img_url
    except Exception as err:
        print(f"[news_images] Serper API image search failed: {err}")

    return None


def prepare_post_images(
    article: dict,
    ticker: str,
) -> list[str]:
    """
    Prepare post image with smart fallback logic.

    Returns:
        []       -> text-only
        [path]   -> exactly one image
    """
    article_url = article.get("url", "") if isinstance(article, dict) else ""
    article_title = article.get("title", "") if isinstance(article, dict) else ""
    clean_ticker = (
        str(ticker).upper().strip().replace("$", "") if ticker else ""
    )

    # ---------------------------------------------------------
    # Priority 1: Extract Original Article Image
    # ---------------------------------------------------------
    og_image_url = _get_article_og_image(article_url)
    if og_image_url:
        img_path = _download_image(og_image_url, "article_img")
        if img_path:
            print(f"[news_images] using original article image: {img_path}")
            return [img_path]

    # ---------------------------------------------------------
    # Priority 2: Serper API Search Fallback
    # ---------------------------------------------------------
    search_query = f"{clean_ticker} {article_title}".strip() if clean_ticker else article_title
    if search_query:
        serper_image_url = _get_serper_search_image(search_query)
        if serper_image_url:
            img_path = _download_image(serper_image_url, "serper_img")
            if img_path:
                print(f"[news_images] using Serper search image: {img_path}")
                return [img_path]

    # ---------------------------------------------------------
    # Priority 3: Binance Logo Backup Fallback
    # ---------------------------------------------------------
    if clean_ticker:
        verified_ticker = _get_verified_ticker(clean_ticker)
        if verified_ticker:
            candidates = _get_logo_candidates(verified_ticker)
            for logo_url in candidates:
                logo_path = _download_image(logo_url, "crypto_logo")
                if logo_path:
                    print(
                        f"[news_images] using Binance crypto logo fallback: {logo_path}"
                    )
                    return [logo_path]

    print("[news_images] all image options failed -> returning text-only post.")
    return []


def cleanup_images(paths: list[str]) -> None:
    """
    Delete temporary downloaded images.
    """
    for path in paths:
        if not path:
            continue
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as err:
            print(f"[news_images] cleanup failed: {path} -> {err}")
