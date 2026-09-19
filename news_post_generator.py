"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

Rules:
- Only Binance-listed crypto assets are allowed.
- Company-only news is rejected when no valid crypto ticker is found.
- Articles already posted are rejected.
- Crypto tickers already posted today can be blocked by main.py.
- AI cannot invent or change the verified ticker.
"""

import re
import json
import random

from groq import Groq

import config as cfg
from news_fetch import fetch_crypto_news
from binance_symbols import (
    get_binance_crypto_tickers,
    is_binance_crypto_ticker,
)


SYSTEM_PROMPT = """You are a professional crypto news writer for Binance Square.

Turn ONE real crypto-asset news article into a concise, natural,
research-style post.

EXACT FORMAT:

Bitcoin ($BTC): Attention-grabbing factual headline

Paragraph 1 explaining what happened.

Paragraph 2 explaining the important development.

Paragraph 3 explaining why the development matters.

The Python program will automatically add:
**$BTC**

STRICT RULES:

- Write ONLY about the specific crypto asset identified by Python.
- Use ONLY facts contained in the article headline and summary.
- Never invent numbers, dates, partnerships, valuations, quotes, or events.
- Never invent a ticker.
- Use the exact ticker provided by Python.
- The title MUST follow:
  Coin Name ($TICKER): Hook
- The title must NOT be all caps.
- Do NOT create a separate risk section.
- Do NOT use bullet points.
- Do NOT use hashtags.
- Do NOT use emojis.
- Do NOT use buy/sell/long/short/target language.
- Do NOT give investment advice.
- Do NOT make unsupported price predictions.
- Use professional, natural English.
- Avoid repetitive AI-style phrases.
- Keep the body around 100-140 words when possible.
- Write exactly 3 short paragraphs.
- Do NOT write the final ticker line.
- Output ONLY valid JSON.
- Do NOT output Markdown fences.

Return exactly:

{
  "title": string,
  "body": string
}
"""


# -------------------------------------------------------------
# Crypto name → ticker
# -------------------------------------------------------------
#
# This is NOT the allowed-coin list.
#
# Binance's live symbol list is used for ticker validation.
# This map only helps when an article writes the full asset name
# instead of the ticker.
# -------------------------------------------------------------

ASSET_NAME_MAP = {
    "BITCOIN CASH": "BCH",
    "BINANCE COIN": "BNB",
    "DOGECOIN": "DOGE",
    "SHIBA INU": "SHIB",
    "INTERNET COMPUTER": "ICP",
    "NEAR PROTOCOL": "NEAR",
    "WORLDCOIN": "WLD",
    "ZCASH": "ZEC",
    "CHAINLINK": "LINK",
    "POLKADOT": "DOT",
    "LITECOIN": "LTC",
    "AVALANCHE": "AVAX",
    "ETHEREUM": "ETH",
    "SOLANA": "SOL",
    "CARDANO": "ADA",
    "BITCOIN": "BTC",
    "RIPPLE": "XRP",
    "TRON": "TRX",
    "TONCOIN": "TON",
    "TON": "TON",
    "UNISWAP": "UNI",
    "ARBITRUM": "ARB",
    "OPTIMISM": "OP",
    "SUI": "SUI",
    "APTOS": "APT",
    "PEPE": "PEPE",
    "BONK": "BONK",
    "AAVE": "AAVE",
    "ZKSYNC": "ZK",
    "STORY": "IP",
}


# -------------------------------------------------------------
# Ticker → readable crypto name
# -------------------------------------------------------------

KNOWN_ASSET_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "BNB": "BNB",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "TRX": "TRON",
    "TON": "Toncoin",
    "LINK": "Chainlink",
    "AVAX": "Avalanche",
    "DOT": "Polkadot",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
    "ZEC": "Zcash",
    "AAVE": "Aave",
    "UNI": "Uniswap",
    "ARB": "Arbitrum",
    "OP": "Optimism",
    "SUI": "Sui",
    "APT": "Aptos",
    "NEAR": "NEAR Protocol",
    "ICP": "Internet Computer",
    "WLD": "Worldcoin",
    "PEPE": "Pepe",
    "SHIB": "Shiba Inu",
    "BONK": "Bonk",
}


def get_candidate_article(
    seen_urls: set,
    blocked_tickers: set | None = None,
) -> dict | None:
    """
    Return ONE eligible crypto article.

    Rules:
    - Already-posted article URL is skipped.
    - Articles without a valid crypto ticker are skipped.
    - Ticker must be currently listed on Binance Spot.
    - Crypto tickers already posted today are skipped.
    - Another eligible crypto article is searched instead.
    """

    articles = fetch_crypto_news()

    candidates = []

    blocked_tickers = {
        str(t).upper()
        for t in (blocked_tickers or set())
    }

    # ---------------------------------------------------------
    # Load current Binance crypto tickers
    # ---------------------------------------------------------

    binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:
        print(
            "[news] Binance symbol list unavailable."
        )

        return None

    for article in articles:

        url = article.get("url")
        headline = article.get("headline", "")
        summary = article.get("summary", "")

        # -----------------------------------------------------
        # Basic validation
        # -----------------------------------------------------

        if not url:
            continue

        if url in seen_urls:
            print(
                f"[news] SKIP — article already posted: "
                f"{headline}"
            )
            continue

        if not headline:
            continue

        if len(summary) <= 40:
            print(
                f"[news] SKIP — summary too short: "
                f"{headline}"
            )
            continue

        # -----------------------------------------------------
        # Detect crypto ticker
        # -----------------------------------------------------

        ticker = _detect_ticker(
            article,
            binance_tickers,
        )

        if not ticker:
            print(
                f"[news] SKIP — no verified Binance crypto: "
                f"{headline}"
            )
            continue

        ticker = ticker.upper()

        # -----------------------------------------------------
        # Same crypto already posted today
        # -----------------------------------------------------

        if ticker in blocked_tickers:
            print(
                f"[news] SKIP — ${ticker} already posted today: "
                f"{headline}"
            )
            continue

        # -----------------------------------------------------
        # Save verified ticker
        # -----------------------------------------------------

        article["ticker"] = ticker

        candidates.append(article)

    # ---------------------------------------------------------
    # No eligible article
    # ---------------------------------------------------------

    if not candidates:
        print(
            "[news] no eligible crypto article found "
            "after Binance + daily ticker filters."
        )

        return None

    # ---------------------------------------------------------
    # Recent pool
    # ---------------------------------------------------------

    pool = candidates[:10]

    article = random.choice(pool)

    print(
        f"[news] selected crypto article: "
        f"${article.get('ticker')} — "
        f"{article.get('headline')}"
    )

    return article


def _detect_ticker(
    article: dict,
    binance_tickers: set[str] | None = None,
) -> str | None:
    """
    Detect a crypto ticker from the article.

    Priority:
    1. Explicit $TICKER
    2. Known crypto asset names
    3. Binance-listed standalone ticker

    IMPORTANT:
    The ticker must exist in Binance's current crypto list.
    """

    if binance_tickers is None:
        binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:
        return None

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

    # ---------------------------------------------------------
    # 1. Explicit $TICKER
    # ---------------------------------------------------------

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        haystack,
    )

    for ticker in explicit_tickers:

        ticker = ticker.upper()

        if ticker in binance_tickers:
            return ticker

    # ---------------------------------------------------------
    # 2. Full crypto asset names
    # ---------------------------------------------------------

    for name in sorted(
        ASSET_NAME_MAP,
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(name)}\b",
            haystack,
        ):

            ticker = ASSET_NAME_MAP[name]

            if ticker in binance_tickers:
                return ticker

    # ---------------------------------------------------------
    # 3. Binance-listed standalone tickers
    # ---------------------------------------------------------

    # Sort longest first.
    # This avoids some partial matching issues.
    possible_tickers = sorted(
        binance_tickers,
        key=len,
        reverse=True,
    )

    for ticker in possible_tickers:

        # Avoid obviously unsafe single-character tickers.
        if len(ticker) < 2:
            continue

        if re.search(
            rf"\b{re.escape(ticker)}\b",
            haystack,
        ):
            return ticker

    return None


def _detect_asset_name(
    ticker: str,
) -> str | None:
    """
    Return a readable asset name.

    For assets not in the small name map, the ticker itself
    is used as the display name.
    """

    if not ticker:
        return None

    ticker = ticker.upper()

    return KNOWN_ASSET_NAMES.get(
        ticker,
        ticker,
    )


def generate_news_post(article: dict) -> dict:
    """
    Generate a Binance Square post ONLY for a verified
    Binance-listed crypto asset.
    """

    # ---------------------------------------------------------
    # Get ticker saved by candidate selector
    # ---------------------------------------------------------

    ticker = article.get("ticker")

    if not ticker:
        ticker = _detect_ticker(article)

    if not ticker:
        raise RuntimeError(
            "Article rejected: no Binance-listed crypto "
            "ticker detected."
        )

    ticker = ticker.upper()

    # ---------------------------------------------------------
    # Verify again against Binance
    # ---------------------------------------------------------

    if not is_binance_crypto_ticker(ticker):
        raise RuntimeError(
            f"Article rejected: ${ticker} is not currently "
            "verified as a Binance Spot crypto asset."
        )

    # ---------------------------------------------------------
    # Get asset name
    # ---------------------------------------------------------

    asset_name = _detect_asset_name(ticker)

    if not asset_name:
        raise RuntimeError(
            f"Article rejected: unable to identify "
            f"crypto asset ${ticker}."
        )

    # ---------------------------------------------------------
    # Groq
    # ---------------------------------------------------------

    client = Groq(
        api_key=cfg.GROQ_API_KEY
    )

    # ---------------------------------------------------------
    # Prompt
    # ---------------------------------------------------------

    user_prompt = f"""Article headline:
{article.get('headline')}

Article summary:
{article.get('summary')}

Source:
{article.get('source', 'unknown')}

Verified Binance crypto asset:
{asset_name}

Verified ticker:
${ticker}

Create a Binance Square crypto news post using ONLY the
article headline and summary.

The article MUST be about:

{asset_name} (${ticker})

TITLE:

Use exactly this structure:

{asset_name} (${ticker}): Hook

BODY:

Write exactly 3 short factual paragraphs.

Use only facts from the article.

Do NOT add:
- hashtags
- emojis
- bullet points
- risk section
- investment advice
- buy/sell language
- long/short language
- target language
- unsupported predictions
- invented statistics
- invented events

Do NOT create or change the ticker.

Do NOT add the final **${ticker}** line.
Python will add it.

Return ONLY:

{{
  "title": string,
  "body": string
}}"""

    # ---------------------------------------------------------
    # Call Groq
    # ---------------------------------------------------------

    completion = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.6,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    raw = (
        completion.choices[0].message.content
        or ""
    )

    # ---------------------------------------------------------
    # Clean response
    # ---------------------------------------------------------

    cleaned = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    try:

        post = json.loads(cleaned)

    except json.JSONDecodeError as err:

        raise RuntimeError(
            f"Model did not return valid JSON: {raw}"
        ) from err

    # ---------------------------------------------------------
    # Validate
    # ---------------------------------------------------------

    title = str(
        post.get("title", "")
    ).strip()

    body = str(
        post.get("body", "")
    ).strip()

    if not title or not body:
        raise RuntimeError(
            "AI returned an empty title or body."
        )

    # ---------------------------------------------------------
    # Verify ticker in title
    # ---------------------------------------------------------

    title_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        title.upper(),
    )

    if title_tickers:

        if title_tickers[0] != ticker:

            raise RuntimeError(
                f"AI used wrong ticker in title: "
                f"${title_tickers[0]} "
                f"instead of ${ticker}"
            )

    # ---------------------------------------------------------
    # Require correct ticker marker
    # ---------------------------------------------------------

    expected_marker = f"(${ticker})"

    if expected_marker not in title.upper():

        raise RuntimeError(
            f"AI title does not contain verified "
            f"ticker ${ticker}: {title}"
        )

    # ---------------------------------------------------------
    # Save final post
    # ---------------------------------------------------------

    post["title"] = title
    post["body"] = body
    post["url"] = article.get("url")
    post["ticker"] = ticker

    return post


def format_news_post(post: dict) -> str:
    """
    Build final Binance Square post.

    Python generates the final ticker line.
    """

    title = str(
        post.get("title", "")
    ).strip()

    body = str(
        post.get("body", "")
    ).strip()

    ticker = post.get("ticker")

    if not ticker:
        raise RuntimeError(
            "Refusing to publish: no crypto ticker."
        )

    ticker = str(
        ticker
    ).upper()

    parts = []

    if title:
        parts.append(title)

    if body:
        parts.append(body)

    # Final ticker line
    parts.append(
        f"**${ticker}**"
    )

    text = "\n\n".join(parts).strip()

    # ---------------------------------------------------------
    # Character limit
    # ---------------------------------------------------------

    if len(text) > cfg.CHAR_LIMIT:

        text = (
            text[:cfg.CHAR_LIMIT]
            .rstrip()
        )

    return text
