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

# IMPORTANT:
# binance_symbols.py is in the project root,
# so do NOT use "src.binance_symbols".
from binance_symbols import is_binance_crypto_ticker


TIMEOUT = 20
MAX_IMAGE_SIZE = 10 * 1024 * 1024

BINANCE_LOGO_BASE = (
    "https://bin.bnbstatic.com"
)


def _get_verified_ticker(
    ticker: str,
) -> str | None:
    """
    Verify ticker using the project's existing
    Binance Spot asset verification system.
    """

    if not ticker:
        return None

    ticker = (
        str(ticker)
        .upper()
        .strip()
        .replace("$", "")
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

    These are ONLY candidates.
    """

    ticker = (
        str(ticker)
        .upper()
        .strip()
        .replace("$", "")
    )

    if not ticker:
        return []

    return [
        (
            f"{BINANCE_LOGO_BASE}"
            f"/static/assets/logos/{ticker}.png"
        ),
        (
            f"{BINANCE_LOGO_BASE}"
            f"/static/assets/logos/{ticker.lower()}.png"
        ),
    ]


def _download_image(
    url: str,
    prefix: str,
) -> str | None:
    """
    Download one image and verify its response.
    """

    if not url:
        return None

    response = None
    path = None

    try:
        print(
            f"[news_images] requesting image: {url}"
        )

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
                "[news_images] rejected image URL "
                "because response is not an image: "
                f"{url}"
            )

            print(
                "[news_images] Content-Type: "
                f"{content_type or 'unknown'}"
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
    # prepare_post_images() will verify that
    # it actually returns an image.
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
        .replace("$", "")
    )

    # ---------------------------------------------------------
    # Verify ticker
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
    # Get logo candidates
    # ---------------------------------------------------------

    candidates = _get_logo_candidates(
        verified_ticker
    )

    if not candidates:
        print(
            f"[news_images] no Binance logo "
            f"candidate for ${verified_ticker} "
            "-> text-only"
        )

        return []

    # ---------------------------------------------------------
    # Try each candidate
    # ---------------------------------------------------------

    for logo_url in candidates:

        print(
            f"[news_images] checking Binance logo "
            f"for ${verified_ticker}: {logo_url}"
        )

        logo_path = _download_image(
            logo_url,
            "crypto_logo",
        )

        if logo_path:

            print(
                f"[news_images] crypto logo ready "
                f"for ${verified_ticker}: {logo_path}"
            )

            # IMPORTANT:
            # Maximum ONE image.
            return [logo_path]

    # ---------------------------------------------------------
    # No valid logo found
    # ---------------------------------------------------------

    print(
        f"[news_images] could not find a valid "
        f"Binance logo for ${verified_ticker} "
        "-> text-only"
    )

    return []


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
