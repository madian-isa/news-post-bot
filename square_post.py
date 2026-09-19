```python
"""
square_post.py

Binance Square posting helper.

Rules:
- Uses the official Binance Skills Hub repository.
- NEVER reuses an old cached Binance Skill.
- Deletes the temporary Skill directory before cloning.
- Uses the official post-image.mjs for image posts.
- Uses the official /content/add API for text-only posts.
- API keys are read only from environment variables.
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


# ---------------------------------------------------------------------------
# Binance Square API
# ---------------------------------------------------------------------------

BASE_URL_V1 = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi"
)

# Official Binance Skills Hub
SKILL_REPO = "https://github.com/binance/binance-skills-hub.git"

# IMPORTANT:
# Do not use a persistent cache here.
# This directory is deleted before every clone.
SKILL_DIR = (
    Path(tempfile.gettempdir())
    / "binance-skills-hub-current"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """
    Get Binance Square OpenAPI key.

    The GitHub Actions workflow should provide:
        BINANCE_SQUARE_OPENAPI_KEY
    """

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
    """
    Find Node.js executable.
    """

    node = shutil.which("node")

    if not node:
        raise RuntimeError(
            "Node.js was not found on PATH."
        )

    return node


def _ensure_fresh_square_skill() -> Path:
    """
    Delete any old cached Binance Skill and clone the
    current official Binance Skills Hub repository.

    This intentionally does NOT reuse an existing directory.
    """

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
            "was not found after cloning."
        )

    print(
        "[square_post] current official Binance "
        "Square Skill ready."
    )

    return script


def _validate_images(
    image_paths: list[str],
) -> list[Path]:
    """
    Validate local image files before sending them
    to the official Binance Skill.
    """

    if not image_paths:
        raise ValueError(
            "No image paths were provided."
        )

    if len(image_paths) > 4:
        raise ValueError(
            "Binance Square supports a maximum of 4 images."
        )

    valid: list[Path] = []

    for index, image_path in enumerate(
        image_paths,
        start=1,
    ):
        path = Path(image_path).expanduser().resolve()

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

        valid.append(path)

        print(
            f"[square_post] image {index}: {path}"
        )

    return valid


# ---------------------------------------------------------------------------
# Text-only post
# ---------------------------------------------------------------------------

def post_text(text: str) -> Optional[str]:
    """
    Publish a text-only Binance Square post.

    This uses the same V1 /content/add endpoint that
    the official Skill uses for publishing.
    """

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
            "contentType": 1,
            "bodyTextOnly": text,
        },
        timeout=60,
    )

    # Binance may return 504 even though the post was accepted.
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
            f"Binance API error "
            f"[{data.get('code')}]: "
            f"{data.get('message')}"
        )

    result = data.get("data") or {}

    share_link = result.get("shareLink")

    if share_link:
        print(
            f"[square_post] text post successful: "
            f"{share_link}"
        )

    return share_link


# ---------------------------------------------------------------------------
# Image post
# ---------------------------------------------------------------------------

def post_with_images(
    text: str,
    image_paths: list[str],
) -> Optional[str]:
    """
    Publish a Binance Square short image post.

    IMPORTANT:
    The actual image upload is handled entirely by the
    current official Binance Skill.

    Flow:
        image
          ↓
        /image/presignedUrl
          ↓
        S3 PUT
          ↓
        /image/imageStatus
          ↓
        /content/add
    """

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot publish an empty Binance Square post."
        )

    images = _validate_images(image_paths)

    print(
        f"[square_post] valid images: {len(images)}"
    )

    # Always remove/re-clone the Skill.
    script = _ensure_fresh_square_skill()

    node = _get_node()

    print(
        f"[square_post] Node.js: {node}"
    )

    # The official Skill expects comma-separated image paths.
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

    # Explicitly pass the key to the official Skill.
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
        print(result.stdout.rstrip())

    if result.stderr:
        print(
            "[square_post] Binance Skill error output:"
        )
        print(result.stderr.rstrip())

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

    # Try to extract the Share Link from the official
    # Skill's normal output.
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

    print(
        "[square_post] image post completed, "
        "but no Share Link was returned."
    )

    return None


# ---------------------------------------------------------------------------
# Generic publisher
# ---------------------------------------------------------------------------

def post(
    text: str,
    image_paths: Optional[list[str]] = None,
) -> Optional[str]:
    """
    Publish either an image post or text-only post.

    If image_paths are supplied, the current official
    Binance Skill is used.

    If no images are supplied, the normal text API is used.
    """

    if image_paths:
        return post_with_images(
            text,
            image_paths,
        )

    return post_text(text)
```

### What changed

The important part is this:

```python
if SKILL_DIR.exists():
    shutil.rmtree(SKILL_DIR, ignore_errors=True)

git clone --depth 1 https://github.com/binance/binance-skills-hub.git ...
```

So every GitHub Actions run:

**old Skill → deleted → fresh official Skill → used.**

The current official source confirms that image upload uses `/image/presignedUrl` through V2, then S3 upload, then image-status polling, and finally `/content/add` through V1.

Also, the official `post-image.mjs` accepts `--images` with up to 4 images and calls `uploadImage()` for each one.

**Your YML does not need to change for this.** `BINANCE_SQUARE_OPENAPI_KEY` can remain exactly as you already have it.

One thing to note: this change will tell us whether the old cached Skill was responsible. If a fresh official Skill still returns **`20005: Can't get presigned url`**, then we know the problem is not your cached Skill and we can focus specifically on Binance's image-upload API/key/account side.
