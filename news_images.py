"""
news_images.py

Prepares ONLY the crypto logo for a crypto news post.

Example:
$ZEC post  -> ZEC logo
$SUPER post -> SUPER logo
$BTC post  -> BTC logo

No article image.
No AI-generated image.
If the coin logo cannot be found, the post will be text-only.
"""

import os
import tempfile
from pathlib import Path

import requests


BINANCE_ASSET_LOGO_URL = (
    "https://www.binance.com/"
    "bapi/asset/v1/public/asset-service/product/currency"
)

TIMEOUT = 15


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
                )
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
        elif "jpeg" in content_type or "jpg" in content_type:
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

                # Safety limit: 10 MB
                if total > 10 * 1024 * 1024:
                    raise ValueError(
                        "Image is larger than 10 MB."
                    )

                file.write(chunk)

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
    Get the Binance asset logo URL for the ticker.
    """

    if not ticker:
        return None

    ticker = ticker.upper().strip()

    try:
        response = requests.get(
            BINANCE_ASSET_LOGO_URL,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as err:
        print(
            f"[news_images] Binance logo lookup failed: "
            f"{err}"
        )
        return None

    assets = data.get("data") or []

    for asset in assets:

        if not isinstance(asset, dict):
            continue

        symbol = str(
            asset.get("asset", "")
        ).upper().strip()

        if symbol != ticker:
            continue

        logo = (
            asset.get("pic")
            or asset.get("icon")
            or asset.get("logo")
        )

        if logo:
            return str(logo)

    print(
        f"[news_images] no Binance logo found for ${ticker}"
    )

    return None


def prepare_post_images(
    article: dict,
    ticker: str,
) -> list[str]:
    """
    Prepare ONLY the crypto logo.

    Article images are intentionally ignored.
    """

    paths = []

    if not ticker:
        print(
            "[news_images] no ticker -> no image"
        )
        return paths

    ticker = ticker.upper().strip()

    # ---------------------------------------------------------
    # ONLY IMAGE — CRYPTO LOGO
    # ---------------------------------------------------------

    logo_url = get_binance_asset_logo_url(
        ticker
    )

    if not logo_url:
        print(
            f"[news_images] no logo available for "
            f"${ticker} -> text-only post"
        )
        return paths

    logo_path = _download_image(
        logo_url,
        "crypto_logo",
    )

    if logo_path:
        print(
            f"[news_images] crypto logo ready for "
            f"${ticker}: {logo_path}"
        )

        paths.append(logo_path)

    print(
        f"[news_images] prepared "
        f"{len(paths)} image(s) for ${ticker}"
    )

    return paths


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
            
