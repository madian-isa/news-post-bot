"""
news_images.py

Prepares ONLY the crypto logo for a crypto news post.

Rules:
- Maximum 1 image.
- Crypto logo only.
- No article image.
- No AI-generated image.
- Does NOT use Binance Web3 token search.
- Verifies the ticker against Binance Spot exchangeInfo first.
- If a verified Binance-hosted logo cannot be confirmed,
  returns text-only.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests


TIMEOUT = 20
MAX_IMAGE_SIZE = 10 * 1024 * 1024

BINANCE_SPOT_BASE = (
    "https://data-api.binance.vision"
)

BINANCE_EXCHANGE_INFO_URL = (
    f"{BINANCE_SPOT_BASE}/api/v3/exchangeInfo"
)

# Binance's static asset CDN.
# We only accept an image if the URL actually returns
# an image and the Binance Spot asset was verified first.
BINANCE_LOGO_BASE = (
    "https://bin.bnbstatic.com/static/assets/logos"
)


def _get_spot_exchange_info(
    ticker: str,
) -> dict | None:
    """
    Verify that the ticker belongs to a Binance Spot asset.

    Binance official Spot API:
        GET /api/v3/exchangeInfo

    We query symbols containing the asset against common
    USDT/BTC/USDC pairs.

    Returns the exchangeInfo response or None.
    """

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    if not ticker:
        return None

    # Try the most common quote assets first.
    quote_assets = (
        "USDT",
        "USDC",
        "FDUSD",
        "BTC",
        "BNB",
        "ETH",
    )

    for quote in quote_assets:

        symbol = f"{ticker}{quote}"

        try:
            response = requests.get(
                BINANCE_EXCHANGE_INFO_URL,
                params={
                    "symbol": symbol,
                },
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "NewsPostBot/1.0"
                    ),
                    "Accept": "application/json",
                },
                timeout=TIMEOUT,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            if not isinstance(data, dict):
                continue

            returned_symbol = str(
                data.get("symbol", "")
            ).upper()

            base_asset = str(
                data.get("baseAsset", "")
            ).upper()

            if (
                returned_symbol == symbol
                and base_asset == ticker
            ):
                print(
                    f"[news_images] Binance Spot "
                    f"verified: {symbol}"
                )

                return data

        except Exception as err:
            print(
                "[news_images] Binance Spot "
                f"verification failed for {symbol}: {err}"
            )

    return None


def _find_verified_spot_asset(
    ticker: str,
) -> bool:
    """
    Return True only when the ticker is verified as a
    Binance Spot base asset.
    """

    info = _get_spot_exchange_info(ticker)

    if not info:
        print(
            f"[news_images] ${ticker} is not "
            "verified through Binance Spot exchangeInfo."
        )
        return False

    return True


def _candidate_logo_urls(
    ticker: str,
) -> list[str]:
    """
    Build Binance-hosted logo candidates.

    These are only candidates. We NEVER assume a URL is
    valid; _download_image() must confirm that Binance
    actually returns an image.
    """

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    if not ticker:
        return []

    return [
        f"{BINANCE_LOGO_BASE}/{ticker}.png",
        f"{BINANCE_LOGO_BASE}/{ticker.lower()}.png",
    ]


def _download_image(
    url: str,
    prefix: str,
) -> str | None:
    """
    Download one verified image.

    The server response MUST identify itself as an image.
    """

    if not url:
        return None

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
                    "image/jpeg,image/*,*/*;q=0.8"
                ),
            },
            timeout=TIMEOUT,
            stream=True,
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
                "[news_images] Binance logo candidate "
                "did not return a supported image: "
                f"{url} "
                f"(Content-Type: {content_type})"
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
            f"{total:,} bytes from Binance."
        )

        return path

    except Exception as err:
        print(
            "[news_images] logo download failed: "
            f"{url} -> {err}"
        )

        return None


def get_binance_asset_logo_url(
    ticker: str,
) -> str | None:
    """
    Return a Binance-hosted logo URL only after the
    ticker has been verified as a Binance Spot asset.

    IMPORTANT:
    No Web3 token search is performed here.
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

    print(
        f"[news_images] looking for verified "
        f"Binance Spot logo for ${ticker}"
    )

    # ---------------------------------------------------------
    # STEP 1
    # Verify ticker against Binance Spot.
    # ---------------------------------------------------------

    if not _find_verified_spot_asset(
        ticker
    ):
        print(
            f"[news_images] ${ticker} failed "
            "Binance Spot verification -> text-only"
        )
        return None

    # ---------------------------------------------------------
    # STEP 2
    # Try Binance-hosted logo candidates.
    # ---------------------------------------------------------

    candidates = _candidate_logo_urls(
        ticker
    )

    for logo_url in candidates:

        print(
            f"[news_images] checking Binance "
            f"logo candidate: {logo_url}"
        )

        # We do NOT return the URL merely because it
        # looks correct. Download validation happens later.
        return logo_url

    print(
        f"[news_images] no Binance logo candidate "
        f"available for ${ticker}"
    )

    return None


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
    # Get Binance-verified logo URL.
    # ---------------------------------------------------------

    logo_url = get_binance_asset_logo_url(
        ticker
    )

    if not logo_url:
        print(
            f"[news_images] no verified Binance "
            f"logo for ${ticker} -> text-only"
        )
        return []

    # ---------------------------------------------------------
    # Download and verify actual image response.
    # ---------------------------------------------------------

    logo_path = _download_image(
        logo_url,
        "crypto_logo",
    )

    if not logo_path:
        print(
            f"[news_images] Binance logo could "
            f"not be downloaded for ${ticker} "
            "-> text-only"
        )
        return []

    print(
        f"[news_images] crypto logo ready "
        f"for ${ticker}: {logo_path}"
    )

    # HARD LIMIT:
    # Never return more than one image.
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
