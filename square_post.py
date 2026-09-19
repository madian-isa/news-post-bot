"""
square_post.py

Publishes Binance Square text or image posts.

Text posts use Binance Square OpenAPI.

Image posts use Binance's official Square Skill:
binance/binance-skills-hub

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
    """Safely mask API key in logs."""

    if not key or len(key) < 10:
        return "****"

    return f"{key[:5]}...{key[-4:]}"


def _check_api_key() -> str:
    """Get Binance Square OpenAPI key."""

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

def post_text(text: str) -> dict:
    """Publish a text-only Binance Square post."""

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
# DEBUG post-image.mjs
# =========================================================

def _debug_post_image_script(
    skill_path: Path,
) -> None:
    """
    Inspect the downloaded post-image.mjs.

    API key references are redacted.
    """

    script = (
        skill_path
        / "scripts"
        / "post-image.mjs"
    )

    if not script.exists():

        print(
            "[square_post] DEBUG: "
            "post-image.mjs not found."
        )

        return

    print(
        "[square_post] DEBUG: inspecting "
        "official post-image.mjs..."
    )

    try:

        script_text = script.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = script_text.splitlines()

        print(
            "[square_post] DEBUG: "
            f"post-image.mjs has {len(lines)} lines."
        )

        keywords = (
            "presigned",
            "presign",
            "upload",
            "image",
            "openapi",
            "content/add",
            "imagestatus",
            "imageStatus",
            "fileticket",
            "fileTicket",
        )

        found = []

        for number, line in enumerate(
            lines,
            start=1,
        ):

            lower = line.lower()

            if any(
                keyword.lower() in lower
                for keyword in keywords
            ):

                found.append(
                    (
                        number,
                        line.strip(),
                    )
                )

        for number, line in found[:120]:

            safe_line = line

            if (
                "BINANCE_SQUARE_OPENAPI_KEY"
                in safe_line
            ):

                safe_line = (
                    "[REDACTED: API key reference]"
                )

            print(
                f"[square_post] DEBUG "
                f"{number}: {safe_line}"
            )

        if not found:

            print(
                "[square_post] DEBUG: "
                "No matching upload lines found."
            )

    except Exception as exc:

        print(
            "[square_post] DEBUG: could not inspect "
            f"post-image.mjs: {exc}"
        )


# =========================================================
# DEBUG lib.mjs
# =========================================================

def _debug_lib_script(
    skill_path: Path,
) -> None:
    """
    Inspect lib.mjs.

    Prints the exact section around the API request
    and image upload logic.

    API key values are never printed.
    """

    script = (
        skill_path
        / "scripts"
        / "lib.mjs"
    )

    if not script.exists():

        print(
            "[square_post] DEBUG: "
            "lib.mjs not found."
        )

        return

    print(
        "[square_post] DEBUG: inspecting "
        "official lib.mjs..."
    )

    try:

        script_text = script.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = script_text.splitlines()

        print(
            "[square_post] DEBUG: "
            f"lib.mjs has {len(lines)} lines."
        )

        # -----------------------------------------------------
        # EXACT CONTEXT
        # -----------------------------------------------------

        print(
            "[square_post] DEBUG lib: "
            "showing exact lines 55-105:"
        )

        for number in range(
            55,
            min(106, len(lines) + 1),
        ):

            safe_line = (
                lines[number - 1]
                .strip()
            )

            # Never expose API key references.
            if (
                "BINANCE_SQUARE_OPENAPI_KEY"
                in safe_line
            ):

                safe_line = (
                    "[REDACTED: API key reference]"
                )

            # Hide obvious API key assignments.
            lower_line = safe_line.lower()

            if (
                "api_key" in lower_line
                or "apikey" in lower_line
            ):

                if "=" in safe_line:

                    left = safe_line.split(
                        "=",
                        1,
                    )[0].strip()

                    safe_line = (
                        f"{left} = "
                        "[REDACTED]"
                    )

            print(
                f"[square_post] DEBUG lib "
                f"{number}: {safe_line}"
            )

        # -----------------------------------------------------
        # KEYWORD SEARCH
        # -----------------------------------------------------

        keywords = (
            "async function api",
            "function api",
            "const api",
            "BASE_URL",
            "presignedUrl",
            "image/presignedUrl",
            "fetch(",
            "headers",
            "X-Square-OpenAPI-Key",
            "clienttype",
            "body:",
            "JSON.stringify",
            "uploadToS3",
            "imageStatus",
        )

        found = []

        for number, line in enumerate(
            lines,
            start=1,
        ):

            lower = line.lower()

            if any(
                keyword.lower() in lower
                for keyword in keywords
            ):

                found.append(
                    (
                        number,
                        line.strip(),
                    )
                )

        print(
            "[square_post] DEBUG lib: "
            "relevant lines:"
        )

        for number, line in found[:250]:

            safe_line = line

            if (
                "BINANCE_SQUARE_OPENAPI_KEY"
                in safe_line
            ):

                safe_line = (
                    "[REDACTED: API key reference]"
                )

            lower_line = safe_line.lower()

            if (
                "api_key" in lower_line
                or "apikey" in lower_line
            ):

                if "=" in safe_line:

                    left = safe_line.split(
                        "=",
                        1,
                    )[0].strip()

                    safe_line = (
                        f"{left} = "
                        "[REDACTED]"
                    )

            print(
                f"[square_post] DEBUG lib "
                f"{number}: {safe_line}"
            )

        if not found:

            print(
                "[square_post] DEBUG lib: "
                "No matching upload lines found."
            )

    except Exception as exc:

        print(
            "[square_post] DEBUG: could not inspect "
            f"lib.mjs: {exc}"
        )


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

            valid_paths.append(path)

        else:

            print(
                "[square_post] image does not exist: "
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

    # ---------------------------------------------------------
    # Maximum 4 images
    # ---------------------------------------------------------

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
    # Official Binance Skill
    # ---------------------------------------------------------

    skill_path = _ensure_square_skill()

    # ---------------------------------------------------------
    # Debug official files
    # ---------------------------------------------------------

    _debug_post_image_script(
        skill_path
    )

    _debug_lib_script(
        skill_path
    )

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
    # Image script
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
    # Build link
    # ---------------------------------------------------------

    if not link and post_id:

        link = (
            "https://www.binance.com/"
            f"en/square/post/{post_id}"
        )

    # ---------------------------------------------------------
    # Soft success
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
        "[square_post] Soft success: "
        f"{soft_success}"
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": soft_success,
        "output": output,
    }
