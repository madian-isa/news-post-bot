"""
news_images.py

Prepares ONLY the crypto logo for a crypto news post.

Rules:
- Maximum 1 image.
- Crypto logo only.
- No article image.
- No AI-generated image.
- No Binance Web3 token search.
- Uses the existing binance_symbols.py verification.
- Never guesses a Web3 token from a ticker.
- If an exact Binance logo cannot be verified, returns text-only.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests

from src.binance_symbols import is_binance_crypto_ticker


TIMEOUT = 20
MAX_IMAGE_SIZE = 10 * 1024 * 1024


# Binance-hosted asset CDN.
#
# IMPORTANT:
# We do NOT blindly trust a guessed URL.
# The URL must return an actual image before
# it is used in the post.
BINANCE_LOGO_BASE = (
    "https://bin.bnbstatic.com"
)


def _get_verified_ticker(
    ticker: str,
) -> str | None:
    """
    Verify ticker using the project's existing
    Binance Spot asset verification system.

    This deliberately uses binance_symbols.py so
    there is only ONE source of truth for whether
    an asset is Binance-listed.
    """

    if not ticker:
        return None

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    if not ticker:
        return None

    try:
        verified = is_binance_crypto_ticker(
            ticker
        )

    except Exception as err:
        print(
            "[news_images] Binance ticker "
            f"verification failed for ${ticker}: {err}"
        )
        return None

    if not verified:
        print(
            f"[news_images] ${ticker} is not "
            "verified by binance_symbols.py."
        )
        return None

    print(
        f"[news_images] Binance Spot asset "
        f"verified: ${ticker}"
    )

    return ticker


def _get_logo_candidates(
    ticker: str,
) -> list[str]:
    """
    Return possible Binance-hosted logo URLs.

    IMPORTANT:
    These are ONLY candidates.

    We never assume that a candidate is valid.
    _download_image() must confirm that Binance
    actually returns an image.

    The list is intentionally small so the bot
    never starts searching arbitrary third-party
    websites for a logo.
    """

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    if not ticker:
        return []

    return [
        f"{BINANCE_LOGO_BASE}/static/assets/logos/{ticker}.png",
        f"{BINANCE_LOGO_BASE}/static/assets/logos/{ticker.lower()}.png",
    ]


def _download_image(
    url: str,
    prefix: str,
) -> str | None:
    """
    Download one image and verify its response.

    The server MUST return an actual image.
    """

    if not url:
        return None

    response = None
    path = None

    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "NewsPostBot/1.0"
                ),
                "Accept": (
                    "image/avif,image/webp,"
                    "image/apng,image/png,"
                    "image/jpeg,image/gif,"
                    "image/*,*/*;q=0.8"
                ),
            },
            timeout=TIMEOUT,
            stream=True,
            allow_redirects=True,
        )

        response.raise_for_status()

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
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
                "[news_images] rejected logo URL "
                f"because response is not an image: "
                f"{url}"
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

        extension = extension_map.get(
            content_type,
            ".png",
        )

        fd, path = tempfile.mkstemp(
            prefix=f"{prefix}_",
            suffix=extension,
        )

        os.close(fd)

        total = 0

        with open(
            path,
            "wb",
        ) as file:

            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):

                if not chunk:
                    continue

                total += len(chunk)

                if total > MAX_IMAGE_SIZE:
                    raise ValueError(
                        "Image is larger than 10 MB."
                    )

                file.write(chunk)

        if total <= 0:
            Path(path).unlink(
                missing_ok=True
            )
            return None

        print(
            f"[news_images] downloaded "
            f"{total:,} bytes."
        )

        return path

    except Exception as err:
        if path:
            Path(path).unlink(
                missing_ok=True
            )

        print(
            "[news_images] image download failed: "
            f"{url} -> {err}"
        )

        return None

    finally:
        if response is not None:
            response.close()


def get_binance_asset_logo_url(
    ticker: str,
) -> str | None:
    """
    Get a Binance-hosted logo candidate only after
    the ticker has been verified by binance_symbols.py.

    No Web3 token search is used.
    """

    verified_ticker = _get_verified_ticker(
        ticker
    )

    if not verified_ticker:
        return None

    candidates = _get_logo_candidates(
        verified_ticker
    )

    if not candidates:
        return None

    # Return the first candidate.
    #
    # The actual image validation happens inside
    # prepare_post_images() through _download_image().
    return candidates[0]


def prepare_post_images(
    article: dict,
    ticker: str,
) -> list[str]:
    """
    Prepare ONLY the crypto logo.

    Returns:
        []       -> text-only
        [path]   -> exactly one image
    """

    if not ticker:
        print(
            "[news_images] no ticker -> no image"
        )
        return []

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    # ---------------------------------------------------------
    # STEP 1
    # Verify against the project's Binance Spot list.
    # ---------------------------------------------------------

    verified_ticker = _get_verified_ticker(
        ticker
    )

    if not verified_ticker:
        print(
            f"[news_images] ${ticker} failed "
            "Binance verification -> text-only"
        )
        return []

    # ---------------------------------------------------------
    # STEP 2
    # Get Binance-hosted logo candidate.
    # ---------------------------------------------------------

    logo_url = get_binance_asset_logo_url(
        verified_ticker
    )

    if not logo_url:
        print(
            f"[news_images] no Binance logo "
            f"candidate for ${verified_ticker} "
            "-> text-only"
        )
        return []

    print(
        f"[news_images] checking Binance logo "
        f"for ${verified_ticker}: {logo_url}"
    )

    # ---------------------------------------------------------
    # STEP 3
    # Download only if Binance actually returns
    # an image.
    # ---------------------------------------------------------

    logo_path = _download_image(
        logo_url,
        "crypto_logo",
    )

    if not logo_path:
        print(
            f"[news_images] could not verify/download "
            f"logo for ${verified_ticker} "
            "-> text-only"
        )
        return []

    print(
        f"[news_images] crypto logo ready "
        f"for ${verified_ticker}: {logo_path}"
    )

    # HARD LIMIT:
    # Exactly one image maximum.
    return [logo_path]


def cleanup_images(
    paths: list[str],
) -> None:
    """
    Delete temporary downloaded images.
    """

    for path in paths:

        if not path:
            continue

        try:
            Path(path).unlink(
                missing_ok=True
            )

        except Exception as err:
            print(
                f"[news_images] cleanup failed: "
                f"{path} -> {err}"
            )
