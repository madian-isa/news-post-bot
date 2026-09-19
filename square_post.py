"""
square_post.py

Publishes Binance Square text or image posts.

Text posts use Binance Square OpenAPI.

Image posts use Binance's official Square Skill:
binance/binance-skills-hub

Image flow:
1. Download/prepare official Binance Square Skill
2. Run post-image.mjs
3. Skill handles image presigning
4. Skill uploads image
5. Skill waits for image processing
6. Skill publishes the Square post

Security:
- API key is read from config/environment.
- API key is never printed in full.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

import config as cfg


# =========================================================
# Binance Square API
# =========================================================

BASE_URL_V1 = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi"
)


# =========================================================
# Official Binance Square Skill
# =========================================================

SKILL_REPO = (
    "https://github.com/binance/"
    "binance-skills-hub.git"
)

SKILL_DIR = (
    Path(tempfile.gettempdir())
    / "binance-skills-hub"
)


# =========================================================
# Helpers
# =========================================================

def _mask(key: str) -> str:
    """
    Safely mask API key in logs.
    """

    if not key or len(key) < 10:
        return "****"

    return f"{key[:5]}...{key[-4:]}"


def _check_api_key() -> str:
    """
    Get Binance Square OpenAPI key.
    """

    api_key = cfg.BINANCE_SQUARE_OPENAPI_KEY

    if not api_key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY "
            "is not set."
        )

    return api_key


# =========================================================
# TEXT POST
# =========================================================

def post_text(
    text: str,
) -> dict:
    """
    Publish a text-only Binance Square post.
    """

    api_key = _check_api_key()

    text = str(text or "").strip()

    if not text:
        raise ValueError(
            "Refusing to publish empty post."
        )

    if len(text) > cfg.CHAR_LIMIT:
        raise ValueError(
            f"Post text is {len(text)} chars, "
            f"over the {cfg.CHAR_LIMIT} limit."
        )

    headers = {
        "Content-Type": "application/json",
        "X-Square-OpenAPI-Key": api_key,
        "clienttype": "binanceSkill",
    }

    payload = {
        "bodyTextOnly": text,
    }

    print(
        f"[square_post] posting text "
        f"({len(text)} chars)..."
    )

    response = requests.post(
        f"{BASE_URL_V1}/content/add",
        json=payload,
        headers=headers,
        timeout=30,
    )

    # Binance can return 504 even if the post
    # was actually accepted.
    if response.status_code == 504:

        print(
            f"[square_post] 504 using key "
            f"{_mask(api_key)} — "
            "submission may already have succeeded."
        )

        return {
            "id": None,
            "link": None,
            "soft_success": True,
        }

    try:

        data = response.json()

    except ValueError:

        data = None

    if (
        not response.ok
        or not data
        or data.get("code") != "000000"
    ):

        code = (
            (data or {}).get(
                "code",
                response.status_code,
            )
        )

        message = (
            (data or {}).get(
                "message",
                "Unknown error",
            )
        )

        raise RuntimeError(
            "Binance Square post failed "
            f"[{code}]: {message}"
        )

    post_id = (
        (data.get("data") or {})
        .get("id")
    )

    link = (
        f"https://www.binance.com/"
        f"en/square/post/{post_id}"
        if post_id
        else None
    )

    print(
        f"[square_post] text post successful: "
        f"{link}"
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": False,
    }


# =========================================================
# OFFICIAL BINANCE SKILL
# =========================================================

def _ensure_square_skill() -> Path:
    """
    Download Binance's official Square Skill
    if it is not already available.
    """

    skill_path = (
        SKILL_DIR
        / "skills"
        / "binance"
        / "square-post"
    )

    post_image_script = (
        skill_path
        / "scripts"
        / "post-image.mjs"
    )

    # Already installed
    if (
        skill_path.exists()
        and post_image_script.exists()
    ):

        print(
            "[square_post] official Binance "
            "Square Skill already available."
        )

        return skill_path

    git = shutil.which("git")

    if not git:
        raise RuntimeError(
            "git is required for Binance image "
            "posting but was not found."
        )

    # Remove incomplete/old copy
    if SKILL_DIR.exists():

        print(
            "[square_post] removing old "
            "Square Skill copy..."
        )

        shutil.rmtree(
            SKILL_DIR,
            ignore_errors=True,
        )

    print(
        "[square_post] downloading official "
        "Binance Square Skill..."
    )

    result = subprocess.run(
        [
            git,
            "clone",
            "--depth",
            "1",
            SKILL_REPO,
            str(SKILL_DIR),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Could not download Binance "
            "Square Skill:\n"
            + result.stderr[-2000:]
        )

    if not post_image_script.exists():

        raise RuntimeError(
            "Downloaded Binance Square Skill "
            "does not contain post-image.mjs."
        )

    print(
        "[square_post] official Binance "
        "Square Skill ready."
    )

    return skill_path


# =========================================================
# IMAGE POST
# =========================================================

def post_with_images(
    text: str,
    image_paths: list[str],
) -> dict:
    """
    Publish a Binance Square post with images.

    Supports up to 4 images.

    This bot normally sends:
        1. News image
        2. Crypto logo
    """

    api_key = _check_api_key()

    text = str(text or "").strip()

    if not text:
        raise ValueError(
            "Refusing to publish empty post."
        )

    if len(text) > cfg.CHAR_LIMIT:
        raise ValueError(
            f"Post text is {len(text)} chars, "
            f"over the {cfg.CHAR_LIMIT} limit."
        )

    # ---------------------------------------------------------
    # Validate image paths
    # ---------------------------------------------------------

    valid_paths = []

    for path in image_paths or []:

        if not path:
            continue

        path = os.path.abspath(
            str(path)
        )

        if os.path.isfile(path):

            valid_paths.append(
                path
            )

        else:

            print(
                f"[square_post] image does not exist: "
                f"{path}"
            )

    # ---------------------------------------------------------
    # No images
    # ---------------------------------------------------------

    if not valid_paths:

        print(
            "[square_post] no valid images; "
            "falling back to text-only."
        )

        return post_text(text)

    # Binance Square Skill supports max 4 images.
    valid_paths = valid_paths[:4]

    print(
        "[square_post] valid images: "
        f"{len(valid_paths)}"
    )

    for index, path in enumerate(
        valid_paths,
        start=1,
    ):

        print(
            f"[square_post] image {index}: "
            f"{path}"
        )

    # ---------------------------------------------------------
    # Check official Binance Skill
    # ---------------------------------------------------------

    skill_path = _ensure_square_skill()

    # ---------------------------------------------------------
    # Check Node.js
    # ---------------------------------------------------------

    node = shutil.which("node")

    if not node:

        print(
            "[square_post] Node.js not available; "
            "falling back to text-only."
        )

        return post_text(text)

    print(
        f"[square_post] Node.js: {node}"
    )

    # ---------------------------------------------------------
    # Image posting script
    # ---------------------------------------------------------

    script = (
        skill_path
        / "scripts"
        / "post-image.mjs"
    )

    if not script.exists():

        raise RuntimeError(
            "Binance Square image posting "
            "script was not found:\n"
            f"{script}"
        )

    # ---------------------------------------------------------
    # Image argument
    #
    # Official skill expects comma-separated
    # local image paths.
    # ---------------------------------------------------------

    image_argument = ",".join(
        valid_paths
    )

    # ---------------------------------------------------------
    # Environment
    # ---------------------------------------------------------

    env = os.environ.copy()

    env[
        "BINANCE_SQUARE_OPENAPI_KEY"
    ] = api_key

    # ---------------------------------------------------------
    # Command
    # ---------------------------------------------------------

    command = [
        node,
        str(script),
        "--text",
        text,
        "--images",
        image_argument,
    ]

    print(
        "[square_post] publishing "
        f"{len(valid_paths)} image(s) "
        "through official Binance Skill..."
    )

    # ---------------------------------------------------------
    # Execute official skill
    # ---------------------------------------------------------

    result = subprocess.run(
        command,
        cwd=str(skill_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    output = (
        result.stdout
        + "\n"
        + result.stderr
    ).strip()

    # Show skill output for debugging.
    if output:

        print(
            "[square_post] Binance Skill output:"
        )

        print(output)

    # ---------------------------------------------------------
    # Skill failed
    # ---------------------------------------------------------

    if result.returncode != 0:

        raise RuntimeError(
            "Binance Square image post failed:\n"
            + output[-4000:]
        )

    # ---------------------------------------------------------
    # Extract post ID/link
    # ---------------------------------------------------------

    post_id = None
    link = None

    for line in output.splitlines():

        line_lower = line.lower().strip()

        # Example:
        # ID: 123456
        if line_lower.startswith("id:"):

            value = (
                line.split(
                    ":",
                    1,
                )[1]
                .strip()
            )

            if (
                value
                and value.lower()
                != "unavailable"
            ):

                post_id = value

        # Example:
        # Link: https://...
        if line_lower.startswith("link:"):

            value = (
                line.split(
                    ":",
                    1,
                )[1]
                .strip()
            )

            if (
                value
                and value.lower()
                != "unavailable"
            ):

                link = value

    # ---------------------------------------------------------
    # Build link if only ID is available
    # ---------------------------------------------------------

    if not link and post_id:

        link = (
            "https://www.binance.com/"
            f"en/square/post/{post_id}"
        )

    # ---------------------------------------------------------
    # Successful submission without ID
    # ---------------------------------------------------------

    soft_success = (
        not bool(post_id)
    )

    print(
        "[square_post] image post completed:"
    )

    print(
        f"[square_post] ID: {post_id}"
    )

    print(
        f"[square_post] Link: {link}"
    )

    print(
        f"[square_post] Soft success: "
        f"{soft_success}"
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": soft_success,
        "output": output,
    }
