"""
square_post.py

Publishes text posts to Binance Square, using the "bodyTextOnly" field —
confirmed working for this account (the "content"/"contentType" field
combo that some docs show returned an "empty content" error here).
"""

import requests

import config as cfg


BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"


def _mask(key: str) -> str:
    if not key or len(key) < 10:
        return "****"

    return f"{key[:5]}...{key[-4:]}"


def post_text(text: str) -> dict:
    api_key = cfg.BINANCE_SQUARE_OPENAPI_KEY

    if not api_key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY is not set in environment."
        )

    if not text or not text.strip():
        raise ValueError("Refusing to publish an empty post.")

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
        "bodyTextOnly": text
    }

    resp = requests.post(
        f"{BASE_URL_V1}/content/add",
        json=payload,
        headers=headers,
        timeout=20,
    )

    if resp.status_code == 504:
        print(
            f"[square_post] Got 504 using key {_mask(api_key)} — "
            "post likely went through server-side but no ID/link "
            "was returned. Verify manually on Binance Square."
        )

        return {
            "id": None,
            "link": None,
            "soft_success": True,
        }

    try:
        data = resp.json()
    except ValueError:
        data = None

    if not resp.ok or not data or data.get("code") != "000000":
        code = (data or {}).get("code", resp.status_code)
        message = (data or {}).get("message", "Unknown error")

        raise RuntimeError(
            f"Binance Square post failed [{code}]: {message}"
        )

    post_id = (data.get("data") or {}).get("id")

    link = (
        f"https://www.binance.com/en/square/post/{post_id}"
        if post_id
        else None
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": False,
    }
