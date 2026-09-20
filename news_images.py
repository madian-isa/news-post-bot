"""
news_images.py

Prepares ONLY the crypto logo for a crypto news post.

Rules:
- Maximum 1 image.
- Crypto logo only.
- No article image.
- No AI-generated image.
- Uses Binance-hosted logo sources.
- If logo cannot be found/downloaded, returns text-only.
"""

import os
import tempfile
from pathlib import Path

import requests


TIMEOUT = 15
MAX_IMAGE_SIZE = 10 * 1024 * 1024


# Binance-hosted logo sources.
# We try more than one official Binance-hosted pattern
# because logo availability can differ between assets.
BINANCE_LOGO_URLS = [
    "https://bin.bnbstatic.com/image/cms/blog/20230404/"
    "{ticker}.png",

    "https://bin.bnbstatic.com/image/cms/blog/20230404/"
    "{ticker}.webp",

    "https://public.bnbstatic.com/image/currencies/"
    "{ticker}.png",
]


def _download_image(
    url: str,
    prefix: str,
) -> str | None:
    """Download one image and return its local path."""

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
                "Accept": "image/avif,image/webp,"
                "image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
            timeout=TIMEOUT,
            stream=True,
        )

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type",
            "",
        ).lower()

        if not content_type.startswith("image/"):
            print(
                f"[news_images] not an image: {url}"
            )
            return None

        if "png" in content_type:
            extension = ".png"
        elif "webp" in content_type:
            extension = ".webp"
        elif "gif" in content_type:
            extension = ".gif"
        elif (
            "jpeg" in content_type
            or "jpg" in content_type
        ):
            extension = ".jpg"
        else:
            extension = ".png"

        fd, path = tempfile.mkstemp(
            prefix=f"{prefix}_",
            suffix=extension,
        )

        os.close(fd)

        total = 0

        with open(path, "wb") as file:
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

        if total == 0:
            Path(path).unlink(
                missing_ok=True
            )
            return None

        return path

    except Exception as err:
        print(
            f"[news_images] logo download failed: "
            f"{url} -> {err}"
        )

        return None


def get_binance_asset_logo_url(
    ticker: str,
) -> str | None:
    """
    Find a Binance-hosted logo URL.

    The previous asset-service/product/currency endpoint
    was incorrect for crypto logos; it currently returns
    fiat-currency conversion data.

    We therefore try Binance-hosted logo URL patterns
    directly.
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
        f"[news_images] looking for Binance logo "
        f"for ${ticker}"
    )

    for template in BINANCE_LOGO_URLS:

        url = template.format(
            ticker=ticker
        )

        try:
            response = requests.head(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "NewsPostBot/1.0"
                    )
                },
                timeout=TIMEOUT,
                allow_redirects=True,
            )

            content_type = response.headers.get(
                "Content-Type",
                "",
            ).lower()

            if (
                response.status_code == 200
                and content_type.startswith("image/")
            ):
                print(
                    f"[news_images] logo found: "
                    f"{url}"
                )

                return url

        except Exception as err:
            print(
                f"[news_images] logo check failed: "
                f"{url} -> {err}"
            )

    print(
        f"[news_images] no Binance-hosted logo "
        f"found for ${ticker}"
    )

    return None


def prepare_post_images(
    article: dict,
    ticker: str,
) -> list[str]:
    """
    Prepare ONLY the crypto logo.

    Article images are intentionally ignored.

    Returns:
        []       -> text-only post
        [path]   -> exactly one logo image
    """

    paths: list[str] = []

    if not ticker:
        print(
            "[news_images] no ticker -> no image"
        )
        return paths

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    # ---------------------------------------------------------
    # ONLY IMAGE — CRYPTO LOGO
    # ---------------------------------------------------------

    logo_url = get_binance_asset_logo_url(
        ticker
    )

    if not logo_url:
        print(
            f"[news_images] no logo available "
            f"for ${ticker} -> text-only post"
        )
        return paths

    logo_path = _download_image(
        logo_url,
        "crypto_logo",
    )

    if logo_path:
        print(
            f"[news_images] crypto logo ready "
            f"for ${ticker}: {logo_path}"
        )

        # Safety: never allow more than one image.
        paths.append(logo_path)

    print(
        f"[news_images] prepared "
        f"{len(paths)} image(s) for ${ticker}"
    )

    return paths[:1]


def cleanup_images(
    paths: list[str],
) -> None:
    """Delete temporary downloaded images."""

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
