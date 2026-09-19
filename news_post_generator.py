"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

IMPORTANT:
Only articles with a valid crypto asset ticker are allowed.
If no valid crypto ticker is detected, the article is skipped.
"""

import re
import json
import random

from groq import Groq
import config as cfg
from news_fetch import fetch_crypto_news


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


def get_candidate_article(seen_urls: set) -> dict | None:
    """
    Return ONE new article only if it contains a valid crypto asset.

    Articles without a valid crypto ticker are skipped.
    """

    articles = fetch_crypto_news()
    candidates = []

    for article in articles:
        url = article.get("url")
        headline = article.get("headline", "")
        summary = article.get("summary", "")

        if not url:
            continue

        if url in seen_urls:
            continue

        if not headline:
            continue

        if len(summary) <= 40:
            continue

        # -----------------------------------------------------
        # HARD CRYPTO-ASSET FILTER
        # -----------------------------------------------------

        ticker = _detect_ticker(article)

        if not ticker:
            print(
                f"[news] SKIP — no valid crypto asset ticker: "
                f"{headline}"
            )
            continue

        candidates.append(article)

    if not candidates:
        print("[news] no valid crypto-asset article found.")
        return None

    # Use a small recent pool for variety.
    pool = candidates[:10]

    article = random.choice(pool)

    print(
        f"[news] selected crypto asset article: "
        f"{article.get('headline')}"
    )

    return article


def _detect_ticker(article: dict) -> str | None:
    """
    Detect ONLY real crypto asset tickers.

    Priority:
    1. Explicit $TICKER
    2. Known crypto asset names
    3. Known standalone crypto tickers

    Company stock tickers such as COIN are NOT included.
    """

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

    # ---------------------------------------------------------
    # 1. Explicit $TICKER
    # ---------------------------------------------------------

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,9})\b",
        haystack,
    )

    for ticker in explicit_tickers:
        if ticker in cfg.KNOWN_TICKERS:
            return ticker

    # ---------------------------------------------------------
    # 2. Crypto asset names ONLY
    # ---------------------------------------------------------

    asset_map = {
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
        "XRP": "XRP",
        "BNB": "BNB",
        "DOGE": "DOGE",
        "TRON": "TRX",
        "TONCOIN": "TON",
        "TON": "TON",
        "TRX": "TRX",
        "ADA": "ADA",
        "AAVE": "AAVE",
        "UNISWAP": "UNI",
        "ARBITRUM": "ARB",
        "OPTIMISM": "OP",
        "SUI": "SUI",
        "APTOS": "APT",
        "PEPE": "PEPE",
        "BONK": "BONK",
        "SHIB": "SHIB",
        "AVAX": "AVAX",
        "DOT": "DOT",
        "LTC": "LTC",
        "BCH": "BCH",
        "ZEC": "ZEC",
        "LINK": "LINK",
        "ICP": "ICP",
        "NEAR": "NEAR",
        "WLD": "WLD",
        "OP": "OP",
        "ARB": "ARB",
        "SUI": "SUI",
        "APT": "APT",
    }

    # Check longer names first.
    for name in sorted(
        asset_map,
        key=len,
        reverse=True,
    ):
        if re.search(
            rf"\b{re.escape(name)}\b",
            haystack,
        ):
            return asset_map[name]

    # ---------------------------------------------------------
    # 3. Known crypto tickers ONLY
    # ---------------------------------------------------------

    for base in cfg.KNOWN_TICKERS:
        # COIN is deliberately excluded.
        if base == "COIN":
            continue

        if re.search(
            rf"\b{re.escape(base)}\b",
            haystack,
        ):
            return base

    return None


def _detect_company_name(
    article: dict,
    ticker: str | None,
) -> str | None:
    """
    Return the crypto asset name for the detected ticker.

    Never invents a crypto asset name.
    """

    name_map = {
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
        "WLD": "World",
        "PEPE": "Pepe",
        "SHIB": "Shiba Inu",
        "BONK": "Bonk",
    }

    if not ticker:
        return None

    return name_map.get(ticker)


def generate_news_post(article: dict) -> dict:
    """
    Generate a post ONLY for an article that already passed
    the crypto-asset filter.
    """

    ticker = _detect_ticker(article)

    # HARD STOP.
    # This prevents AI from creating a fake ticker.
    if not ticker:
        raise RuntimeError(
            "Article rejected: no valid crypto asset ticker detected."
        )

    company_name = _detect_company_name(
        article,
        ticker,
    )

    if not company_name:
        raise RuntimeError(
            f"Article rejected: unknown crypto asset ticker ${ticker}."
        )

    client = Groq(api_key=cfg.GROQ_API_KEY)

    user_prompt = f"""Article headline:
{article.get('headline')}

Article summary:
{article.get('summary')}

Source:
{article.get('source', 'unknown')}

Verified crypto asset:
{company_name}

Verified ticker:
${ticker}

Create a Binance Square crypto news post using ONLY the article information.

The article MUST be about:
{company_name} (${ticker})

TITLE:

Use exactly:

{company_name} (${ticker}): Hook

BODY:

Write exactly 3 short factual paragraphs.

Do NOT add:
- hashtags
- emojis
- bullet points
- risk section
- investment advice
- buy/sell language
- long/short language
- target language
- predictions

Do NOT create or change the ticker.

Do NOT add the final **${ticker}** line.
Python will add it.

Return ONLY:

{{
  "title": string,
  "body": string
}}"""

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

    raw = completion.choices[0].message.content or ""

    cleaned = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        post = json.loads(cleaned)

    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Model did not return valid JSON: {raw}"
        ) from err

    # ---------------------------------------------------------
    # Final validation
    # ---------------------------------------------------------

    title = str(post.get("title", "")).strip()
    body = str(post.get("body", "")).strip()

    if not title or not body:
        raise RuntimeError(
            "AI returned an empty title or body."
        )

    # Prevent AI from changing the verified ticker.
    title_ticker = re.findall(
        r"\$([A-Z][A-Z0-9]{1,9})\b",
        title.upper(),
    )

    if title_ticker and title_ticker[0] != ticker:
        raise RuntimeError(
            f"AI used wrong ticker in title: "
            f"${title_ticker[0]} instead of ${ticker}"
        )

    post["title"] = title
    post["body"] = body
    post["url"] = article.get("url")
    post["ticker"] = ticker

    return post


def format_news_post(post: dict) -> str:
    """
    Build final Binance Square post.

    The final ticker line is generated by Python.
    """

    title = post.get("title", "").strip()
    body = post.get("body", "").strip()
    ticker = post.get("ticker")

    # HARD STOP: never publish without ticker.
    if not ticker:
        raise RuntimeError(
            "Refusing to publish: no crypto ticker."
        )

    parts = []

    if title:
        parts.append(title)

    if body:
        parts.append(body)

    # Python-generated final ticker line.
    parts.append(f"**${ticker}**")

    text = "\n\n".join(parts).strip()

    if len(text) > cfg.CHAR_LIMIT:
        text = text[:cfg.CHAR_LIMIT].rstrip()

    return text
