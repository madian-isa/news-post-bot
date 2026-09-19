"""
square_post.py

Publishes Binance Square text or image posts.

Text posts use the existing direct OpenAPI endpoint.

Image posts use Binance's official Square Skill:
binance/binance-skills-hub

The skill handles:
- image presigning
- upload
- processing polling
- imageList
- final Square publication
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests

import config as cfg


BASE_URL_V1 = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi"
)

SKILL_REPO = (
    "https://github.com/binance/"
    "binance-skills-hub.git"
)

SKILL_DIR = Path(
    tempfile.gettempdir()
) / "binance-skills-hub"


def _mask(key: str) -> str:
    if not key or len(key) < 10:
        return "****"

    return f"{key[:5]}...{key[-4:]}"


def _check_api_key() -> str:
    api_key = cfg.BINANCE_SQUARE_OPENAPI_KEY

    if not api_key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY is not set."
        )

    return api_key


def post_text(
    text: str,
) -> dict:
    """
    Publish a text-only Binance Square post.
    """

    api_key = _check_api_key()

    if not text or not text.strip():
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

    response = requests.post(
        f"{BASE_URL_V1}/content/add",
        json=payload,
        headers=headers,
        timeout=30,
    )

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
            f"Binance Square post failed "
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

    return {
        "id": post_id,
        "link": link,
        "soft_success": False,
    }


def _ensure_square_skill() -> Path:
    """
    Download Binance's official Square Skill if needed.
    """

    skill_path = (
        SKILL_DIR
        / "skills"
        / "binance"
        / "square-post"
    )

    if (
        skill_path.exists()
        and (
            skill_path / "scripts" / "post-image.mjs"
        ).exists()
    ):
        return skill_path

    git = shutil.which("git")

    if not git:
        raise RuntimeError(
            "git is required for Binance image "
            "posting but was not found."
        )

    if SKILL_DIR.exists():

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
            "Could not download Binance Square Skill:\n"
            + result.stderr[-2000:]
        )

    if not (
        skill_path
        / "scripts"
        / "post-image.mjs"
    ).exists():

        raise RuntimeError(
            "Downloaded Binance Square Skill does "
            "not contain post-image.mjs."
        )

    return skill_path


def post_with_images(
    text: str,
    image_paths: list[str],
) -> dict:
    """
    Publish a short Binance Square image post.

    Binance's current image-post skill supports up to
    4 images. This bot normally sends max 2:
        1. news image
        2. crypto logo
    """

    api_key = _check_api_key()

    if not text or not text.strip():
        raise ValueError(
            "Refusing to publish empty post."
        )

    if len(text) > cfg.CHAR_LIMIT:
        raise ValueError(
            f"Post text is {len(text)} chars, "
            f"over the {cfg.CHAR_LIMIT} limit."
        )

    # Remove invalid paths.
    valid_paths = []

    for path in image_paths or []:

        if not path:
            continue

        if os.path.isfile(path):
            valid_paths.append(
                os.path.abspath(path)
            )

    # ---------------------------------------------------------
    # No image → normal text post
    # ---------------------------------------------------------

    if not valid_paths:

        print(
            "[square_post] no valid images; "
            "falling back to text-only."
        )

        return post_text(text)

    # Binance Skill allows max 4 images.
    valid_paths = valid_paths[:4]

    skill_path = _ensure_square_skill()

    node = shutil.which("node")

    if not node:

        print(
            "[square_post] Node.js not available; "
            "falling back to text-only."
        )

        return post_text(text)

    script = (
        skill_path
        / "scripts"
        / "post-image.mjs"
    )

    # ---------------------------------------------------------
    # The official skill expects:
    #
    # --text
    # --images
    #
    # comma-separated local paths
    # ---------------------------------------------------------

    image_argument = ",".join(
        valid_paths
    )

    env = os.environ.copy()

    env[
        "BINANCE_SQUARE_OPENAPI_KEY"
    ] = api_key

    command = [
        node,
        str(script),
        "--text",
        text,
        "--images",
        image_argument,
    ]

    print(
        f"[square_post] publishing "
        f"{len(valid_paths)} image(s) "
        f"through official Binance Skill..."
    )

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

    print(
        output
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Binance Square image post failed:\n"
            + output[-4000:]
        )

    # ---------------------------------------------------------
    # Try to extract ID/link from official skill output.
    # ---------------------------------------------------------

    post_id = None
    link = None

    for line in output.splitlines():

        line_lower = line.lower()

        if line_lower.startswith("id:"):

            value = line.split(
                ":",
                1,
            )[1].strip()

            if value and value.lower() != "unavailable":
                post_id = value

        if line_lower.startswith("link:"):

            value = line.split(
                ":",
                1,
            )[1].strip()

            if (
                value
                and value.lower() != "unavailable"
            ):
                link = value

    # Some versions may print the URL directly.
    if not link and post_id:

        link = (
            "https://www.binance.com/"
            f"en/square/post/{post_id}"
        )

    # ---------------------------------------------------------
    # Official skill treats successful 504 submission as
    # success even if ID/link is unavailable.
    # ---------------------------------------------------------

    return {
        "id": post_id,
        "link": link,
        "soft_success": (
            not bool(post_id)
        ),
        "output": output,
    }
