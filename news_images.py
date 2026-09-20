"""
news_images.py

Prepares ONLY the crypto logo for a crypto news post.

Rules:
- Maximum 1 image.
- Crypto logo only.
- No article image.
- No AI-generated image.
- Uses the current official Binance Web3
  query-token-info Skill.
- If the logo cannot be found, returns text-only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests


TIMEOUT = 20

MAX_IMAGE_SIZE = 10 * 1024 * 1024

BINANCE_SKILLS_REPO = (
    "https://github.com/binance/"
    "binance-skills-hub.git"
)

BINANCE_SKILL_DIR = (
    Path(tempfile.gettempdir())
    / "binance-skills-hub-image"
)

BINANCE_WEB3_SKILL = (
    BINANCE_SKILL_DIR
    / "skills"
    / "binance-web3"
    / "query-token-info"
)

BINANCE_TOKEN_CLI = (
    BINANCE_WEB3_SKILL
    / "scripts"
    / "cli.mjs"
)

BINANCE_ICON_BASE = (
    "https://bin.bnbstatic.com"
)


def _ensure_binance_token_skill() -> bool:
    """
    Clone the current official Binance Skills Hub
    if the query-token-info Skill is not available.
    """

    if BINANCE_TOKEN_CLI.exists():
        return True

    try:
        if BINANCE_SKILL_DIR.exists():
            shutil.rmtree(
                BINANCE_SKILL_DIR,
                ignore_errors=True,
            )

        print(
            "[news_images] cloning current official "
            "Binance token-info Skill..."
        )

        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                BINANCE_SKILLS_REPO,
                str(BINANCE_SKILL_DIR),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(
                "[news_images] Binance Skill clone failed:"
            )
            print(
                result.stderr.strip()
            )
            return False

        if not BINANCE_TOKEN_CLI.exists():
            print(
                "[news_images] Binance token-info CLI "
                "was not found."
            )
            return False

        print(
            "[news_images] official Binance "
            "token-info Skill ready."
        )

        return True

    except Exception as err:
        print(
            "[news_images] Binance Skill setup failed: "
            f"{err}"
        )
        return False


def _run_binance_token_search(
    ticker: str,
) -> dict | None:
    """
    Search Binance Web3 token metadata by ticker.

    Official Skill command:

    node cli.mjs search
        '{"keyword":"SUPER","chainIds":"1,56,8453,CT_501"}'
    """

    if not ticker:
        return None

    if not _ensure_binance_token_skill():
        return None

    params = {
        "keyword": ticker,
        "chainIds": "1,56,8453,CT_501",
    }

    try:
        result = subprocess.run(
            [
                "node",
                str(BINANCE_TOKEN_CLI),
                "search",
                json.dumps(params),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )

        stdout = (
            result.stdout or ""
        ).strip()

        stderr = (
            result.stderr or ""
        ).strip()

        if result.returncode != 0:
            print(
                "[news_images] Binance token search "
                "failed."
            )

            if stderr:
                print(
                    f"[news_images] {stderr}"
                )

            return None

        if not stdout:
            print(
                "[news_images] Binance token search "
                "returned empty output."
            )
            return None

        # -----------------------------------------------------
        # Try the whole output first.
        # -----------------------------------------------------

        try:
            data = json.loads(stdout)

            if isinstance(data, dict):
                return data

            if isinstance(data, list):
                return {
                    "data": data
                }

        except json.JSONDecodeError:
            pass

        # -----------------------------------------------------
        # Some CLIs may print additional text.
        # Find JSON-looking lines/blocks.
        # -----------------------------------------------------

        lines = stdout.splitlines()

        for line in reversed(lines):

            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)

                if isinstance(data, dict):
                    return data

                if isinstance(data, list):
                    return {
                        "data": data
                    }

            except json.JSONDecodeError:
                continue

        print(
            "[news_images] could not parse Binance "
            "token search output."
        )

        print(
            f"[news_images] raw output: {stdout[:2000]}"
        )

        return None

    except Exception as err:
        print(
            "[news_images] Binance token search "
            f"exception: {err}"
        )
        return None


def _extract_search_items(
    result: dict | None,
) -> list[dict]:
    """Extract token search results from Binance output."""

    if not result:
        return []

    candidates = []

    for key in (
        "data",
        "result",
        "tokens",
        "list",
        "items",
    ):
        value = result.get(key)

        if isinstance(value, list):
            candidates.extend(
                item
                for item in value
                if isinstance(item, dict)
            )

        elif isinstance(value, dict):
            candidates.append(value)

    if not candidates:
        if any(
            key in result
            for key in (
                "symbol",
                "contractAddress",
                "address",
                "tokenAddress",
            )
        ):
            candidates.append(result)

    return candidates


def _get_value(
    item: dict,
    *keys: str,
):
    """Return the first existing value."""

    for key in keys:

        if key in item:
            value = item.get(key)

            if value not in (
                None,
                "",
            ):
                return value

    return None


def _find_matching_token(
    items: list[dict],
    ticker: str,
) -> dict | None:
    """
    Prefer an exact symbol/ticker match.
    """

    ticker = ticker.upper().strip()

    # ---------------------------------------------------------
    # Exact symbol match.
    # ---------------------------------------------------------

    for item in items:

        symbol = _get_value(
            item,
            "symbol",
            "tokenSymbol",
        )

        if (
            symbol
            and str(symbol).upper().strip()
            == ticker
        ):
            return item

    # ---------------------------------------------------------
    # Exact ticker match.
    # ---------------------------------------------------------

    for item in items:

        token_ticker = _get_value(
            item,
            "ticker",
            "tokenTicker",
        )

        if (
            token_ticker
            and str(token_ticker).upper().strip()
            == ticker
        ):
            return item

    return None


def _get_token_contract(
    item: dict,
) -> tuple[str, str] | None:
    """
    Extract chain ID + contract address.

    Returns:
        (chain_id, contract_address)
    """

    contract = _get_value(
        item,
        "contractAddress",
        "contract",
        "address",
        "tokenAddress",
    )

    if not contract:
        return None

    chain_id = _get_value(
        item,
        "chainId",
        "chainID",
    )

    if not chain_id:
        return None

    return (
        str(chain_id),
        str(contract),
    )


def _run_binance_token_meta(
    chain_id: str,
    contract_address: str,
) -> dict | None:
    """
    Query official Binance token metadata.

    The metadata endpoint returns the token icon.
    """

    params = {
        "chainId": chain_id,
        "contractAddress": contract_address,
    }

    try:
        result = subprocess.run(
            [
                "node",
                str(BINANCE_TOKEN_CLI),
                "meta",
                json.dumps(params),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )

        stdout = (
            result.stdout or ""
        ).strip()

        stderr = (
            result.stderr or ""
        ).strip()

        if result.returncode != 0:
            print(
                "[news_images] Binance token meta "
                "query failed."
            )

            if stderr:
                print(
                    f"[news_images] {stderr}"
                )

            return None

        if not stdout:
            return None

        try:
            data = json.loads(stdout)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

        for line in reversed(
            stdout.splitlines()
        ):

            line = line.strip()

            if not line:
                continue

            try:
                data = json.loads(line)

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                continue

        return None

    except Exception as err:
        print(
            "[news_images] Binance token meta "
            f"exception: {err}"
        )
        return None


def _extract_icon(
    metadata: dict | None,
) -> str | None:
    """Extract and normalize Binance icon URL."""

    if not metadata:
        return None

    candidates = [
        metadata,
        metadata.get("data")
        if isinstance(
            metadata.get("data"),
            dict,
        )
        else None,
        metadata.get("result")
        if isinstance(
            metadata.get("result"),
            dict,
        )
        else None,
    ]

    for item in candidates:

        if not isinstance(item, dict):
            continue

        icon = _get_value(
            item,
            "icon",
            "logo",
            "logoUrl",
            "iconUrl",
        )

        if not icon:
            continue

        icon = str(icon).strip()

        if not icon:
            continue

        if icon.startswith(
            "https://"
        ):
            return icon

        if icon.startswith(
            "http://"
        ):
            return icon.replace(
                "http://",
                "https://",
                1,
            )

        if icon.startswith("/"):
            return (
                BINANCE_ICON_BASE
                + icon
            )

        return (
            BINANCE_ICON_BASE
            + "/"
            + icon
        )

    return None


def get_binance_asset_logo_url(
    ticker: str,
) -> str | None:
    """
    Find the official Binance-hosted token logo.

    Flow:

    ticker
      ↓
    Binance official token search
      ↓
    exact symbol match
      ↓
    chain + contract
      ↓
    Binance token metadata
      ↓
    icon
      ↓
    https://bin.bnbstatic.com + relative path
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
        f"[news_images] looking for official "
        f"Binance logo for ${ticker}"
    )

    search_result = (
        _run_binance_token_search(
            ticker
        )
    )

    items = _extract_search_items(
        search_result
    )

    if not items:
        print(
            f"[news_images] Binance token search "
            f"returned no results for ${ticker}"
        )
        return None

    token = _find_matching_token(
        items,
        ticker,
    )

    if not token:
        print(
            f"[news_images] no exact Binance token "
            f"match for ${ticker}"
        )
        return None

    contract_info = _get_token_contract(
        token
    )

    if not contract_info:
        print(
            f"[news_images] token found for "
            f"${ticker}, but no chain/contract "
            "was returned."
        )
        return None

    chain_id, contract_address = (
        contract_info
    )

    print(
        f"[news_images] matched ${ticker} "
        f"on chain {chain_id}"
    )

    metadata = _run_binance_token_meta(
        chain_id,
        contract_address,
    )

    logo_url = _extract_icon(
        metadata
    )

    if not logo_url:
        print(
            f"[news_images] Binance metadata "
            f"has no icon for ${ticker}"
        )
        return None

    print(
        f"[news_images] official Binance logo found: "
        f"{logo_url}"
    )

    return logo_url


def _download_image(
    url: str,
    prefix: str,
) -> str | None:
    """Download one verified image."""

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
                    "image/apng,image/svg+xml,"
                    "image/*,*/*;q=0.8"
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
        )

        if not content_type.startswith(
            "image/"
        ):
            print(
                "[news_images] Binance icon URL "
                "did not return an image: "
                f"{url}"
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

                if (
                    total
                    > MAX_IMAGE_SIZE
                ):
                    raise ValueError(
                        "Image is larger than "
                        "10 MB."
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
        print(
            "[news_images] logo download failed: "
            f"{url} -> {err}"
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

    logo_url = (
        get_binance_asset_logo_url(
            ticker
        )
    )

    if not logo_url:
        print(
            f"[news_images] no official Binance "
            f"logo available for ${ticker} "
            "-> text-only post"
        )
        return []

    logo_path = _download_image(
        logo_url,
        "crypto_logo",
    )

    if not logo_path:
        print(
            f"[news_images] failed to download "
            f"logo for ${ticker} "
            "-> text-only post"
        )
        return []

    print(
        f"[news_images] crypto logo ready "
        f"for ${ticker}: {logo_path}"
    )

    # Hard limit: exactly one image maximum.
    return [logo_path]


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
