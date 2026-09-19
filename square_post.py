"""
square_post.py

Binance Square posting helper.

Uses the current official Binance Skills Hub repository.
The old temporary/cached Skill is removed before every clone.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

from src import config as cfg


BASE_URL_V1 = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi"
)

SKILL_REPO = (
    "https://github.com/binance/binance-skills-hub.git"
)

SKILL_DIR = (
    Path(tempfile.gettempdir())
    / "binance-skills-hub-current"
)


def _get_api_key() -> str:
    key = os.getenv("BINANCE_SQUARE_OPENAPI_KEY")

    if not key:
        key = getattr(
            cfg,
            "BINANCE_SQUARE_OPENAPI_KEY",
            None,
        )

    if not key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY is missing."
        )

    return key.strip()


def _get_node() -> str:
    node = shutil.which("node")

    if not node:
        raise RuntimeError(
            "Node.js was not found on PATH."
        )

    return node


def _ensure_fresh_square_skill() -> Path:
    print(
        "[square_post] removing old cached Binance Skill..."
    )

    if SKILL_DIR.exists():
        shutil.rmtree(
            SKILL_DIR,
            ignore_errors=True,
        )

    print(
        "[square_post] cloning current official "
        "Binance Square Skill..."
    )

    result = subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            SKILL_REPO,
            str(SKILL_DIR),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Failed to clone official Binance Skills Hub.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    script = (
        SKILL_DIR
        / "skills"
        / "binance"
        / "square-post"
        / "scripts"
        / "post-image.mjs"
    )

    if not script.exists():
        raise RuntimeError(
            "Official Binance Square post-image.mjs "
            "was not found."
        )

    print(
        "[square_post] current official Binance "
        "Square Skill ready."
    )

    return script


def _validate_images(
    image_paths: list[str],
) -> list[Path]:

    if not image_paths:
        raise ValueError(
            "No image paths were provided."
        )

    if len(image_paths) > 4:
        raise ValueError(
            "Binance Square supports a maximum of 4 images."
        )

    valid_images: list[Path] = []

    for index, image_path in enumerate(
        image_paths,
        start=1,
    ):
        path = Path(
            image_path
        ).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Image {index} does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Image {index} is not a file: {path}"
            )

        if path.stat().st_size <= 0:
            raise ValueError(
                f"Image {index} is empty: {path}"
            )

        valid_images.append(path)

        print(
            f"[square_post] image {index}: {path}"
        )

    return valid_images


def post_text(
    text: str,
) -> Optional[str]:

    api_key = _get_api_key()

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot publish an empty Binance Square post."
        )

    print(
        f"[square_post] posting text ({len(text)} chars)..."
    )

    response = requests.post(
        f"{BASE_URL_V1}/content/add",
        headers={
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        },
        json={
            "bodyTextOnly": text,
        },
        timeout=60,
    )

    if response.status_code == 504:
        print(
            "[square_post] Binance returned 504 after "
            "publish request; treating as soft success."
        )
        return None

    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(
            "Binance returned a non-JSON response:\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:1000]}"
        ) from exc

    if data.get("code") != "000000":
        raise RuntimeError(
            "Binance API error "
            f"[{data.get('code')}]: "
            f"{data.get('message')}"
        )

    result = data.get("data") or {}

    share_link = result.get("shareLink")

    if share_link:
        print(
            "[square_post] text post successful: "
            f"{share_link}"
        )

    return share_link


def post_with_images(
    text: str,
    image_paths: list[str],
) -> Optional[str]:

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot publish an empty Binance Square post."
        )

    images = _validate_images(
        image_paths
    )

    print(
        f"[square_post] valid images: {len(images)}"
    )

    script = _ensure_fresh_square_skill()

    node = _get_node()

    print(
        f"[square_post] Node.js: {node}"
    )

    image_argument = ",".join(
        str(path)
        for path in images
    )

    command = [
        node,
        str(script),
        "--text",
        text,
        "--images",
        image_argument,
    ]

    env = os.environ.copy()

    env["BINANCE_SQUARE_OPENAPI_KEY"] = (
        _get_api_key()
    )

    print(
        "[square_post] publishing "
        f"{len(images)} image(s) through "
        "current official Binance Skill..."
    )

    result = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.stdout:
        print(
            "[square_post] Binance Skill output:"
        )
        print(
            result.stdout.rstrip()
        )

    if result.stderr:
        print(
            "[square_post] Binance Skill error output:"
        )
        print(
            result.stderr.rstrip()
        )

    if result.returncode != 0:
        combined = "\n".join(
            part
            for part in (
                result.stdout.strip(),
                result.stderr.strip(),
            )
            if part
        )

        raise RuntimeError(
            "Binance Square image post failed:\n"
            + combined
        )

    for line in result.stdout.splitlines():
        line = line.strip()

        if line.startswith("Link:"):
            link = line.split(
                "Link:",
                1,
            )[1].strip()

            if link and link != "unavailable":
                print(
                    "[square_post] image post successful: "
                    f"{link}"
                )
                return link

    return None


def post(
    text: str,
    image_paths: Optional[list[str]] = None,
) -> Optional[str]:

    if image_paths:
        return post_with_images(
            text,
            image_paths,
        )

    return post_text(text)
