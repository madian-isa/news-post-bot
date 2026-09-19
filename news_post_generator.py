"""
news_post_generator.py

Generates short, factual Binance Square news posts.

Format:

Bitcoin ($BTC): Hits $81K as US bond yields rebound on global oil woes

Paragraph 1.

Paragraph 2.

Paragraph 3.

**$BTC**

Only uses facts from the real Finnhub article.
"""

import re
import json
import random

from groq import Groq
import config as cfg
from news_fetch import fetch_crypto_news


SYSTEM_PROMPT = """You are a professional financial and crypto news writer for Binance Square.

Turn ONE real news article into a concise, natural, research-style post.

EXACT FORMAT:

Coin Name ($TICKER): Attention-grabbing headline

Paragraph 1 explaining what happened.

Paragraph 2 explaining the important development.

Paragraph 3 explaining why the development matters.

The Python program will automatically add the final:
**$TICKER**

STRICT RULES:

- Use ONLY facts contained in the article headline and summary.
- Never invent numbers, dates, partnerships, valuations, quotes, or events.
- Never invent a ticker.
- If a ticker is provided, use that exact ticker.
- The title MUST follow this format:
  Coin/Company Name ($TICKER): Hook
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
- Write 3 short paragraphs.
- Do not write the final ticker line yourself.
- Output ONLY valid JSON.
- Do NOT output Markdown fences.

Return exactly:

{
  "title": string,
  "body": string
}
"""


def get_candidate_article(seen_urls: set) -> dict | None:
    """Returns one Finnhub article not already covered."""

    articles = fetch_crypto_news()

    candidates = [
        a
        for a in articles
        if a.get("url")
        and a["url"] not in seen_urls
        and a.get("headline")
        and len((a.get("summary") or "")) > 40
    ]

    if not candidates:
        return None

    pool = candidates[:10] or candidates

    return random.choice(pool)


def _detect_ticker(article: dict) -> str | None:
    """
    Detect ticker from:
    1. Explicit $TICKER mentions
    2. Known asset/company names
    3. Known standalone tickers

    Never invents a ticker.
    """

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

    # ---------------------------------------------------------
    # 1. Explicit $TICKER in article
    # ---------------------------------------------------------

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,9})\b",
        haystack,
    )

    for ticker in explicit_tickers:
        if ticker in cfg.KNOWN_TICKERS:
            return ticker

    # ---------------------------------------------------------
    # 2. Known asset/company names
    # ---------------------------------------------------------

    asset_map = {
        "BITCOIN": "BTC",
        "ETHEREUM": "ETH",
        "BINANCE COIN": "BNB",
        "BNB": "BNB",
        "SOLANA": "SOL",
        "XRP": "XRP",
        "CARDANO": "ADA",
        "ADA": "ADA",
        "DOGECOIN": "DOGE",
        "DOGE": "DOGE",
        "TRON": "TRX",
        "TRX": "TRX",
        "TONCOIN": "TON",
        "TON": "TON",
        "CHAINLINK": "LINK",
        "AVALANCHE": "AVAX",
        "POLKADOT": "DOT",
        "LITECOIN": "LTC",
        "BITCOIN CASH": "BCH",
        "ZCASH": "ZEC",
        "AAVE": "AAVE",
        "UNISWAP": "UNI",
        "ARBITRUM": "ARB",
        "OPTIMISM": "OP",
        "SUI": "SUI",
        "APTOS": "APT",
        "NEAR PROTOCOL": "NEAR",
        "INTERNET COMPUTER": "ICP",
        "WORLDCOIN": "WLD",
        "WORLD": "WLD",
        "PEPE": "PEPE",
        "SHIBA INU": "SHIB",
        "BONK": "BONK",
        "COINBASE": "COIN",
    }

    # Longer names first so "BITCOIN CASH" is checked
    # before "BITCOIN".
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
    # 3. Known standalone ticker
    # ---------------------------------------------------------

    for base in cfg.KNOWN_TICKERS:
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
    Detect the company/asset name for the title.
    Never invents a name.
    """

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

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
        "COIN": "Coinbase",
    }

    if ticker and ticker in name_map:
        expected_name = name_map[ticker]

        # Confirm the name is actually present in the article
        # for mapped assets.
        search_names = {
            "BTC": ["BITCOIN"],
            "ETH": ["ETHEREUM"],
            "BNB": ["BINANCE COIN", "BNB"],
            "SOL": ["SOLANA"],
            "XRP": ["XRP"],
            "ADA": ["CARDANO", "ADA"],
            "DOGE": ["DOGECOIN", "DOGE"],
            "TRX": ["TRON", "TRX"],
            "TON": ["TONCOIN", "TON"],
            "LINK": ["CHAINLINK"],
            "AVAX": ["AVALANCHE"],
            "DOT": ["POLKADOT"],
            "LTC": ["LITECOIN"],
            "BCH": ["BITCOIN CASH"],
            "ZEC": ["ZCASH"],
            "AAVE": ["AAVE"],
            "UNI": ["UNISWAP"],
            "ARB": ["ARBITRUM"],
            "OP": ["OPTIMISM"],
            "SUI": ["SUI"],
            "APT": ["APTOS"],
            "NEAR": ["NEAR PROTOCOL"],
            "ICP": ["INTERNET COMPUTER"],
            "WLD": ["WORLDCOIN", "WORLD"],
            "PEPE": ["PEPE"],
            "SHIB": ["SHIBA INU"],
            "BONK": ["BONK"],
            "COIN": ["COINBASE"],
        }

        for name in search_names.get(ticker, []):
            if re.search(
                rf"\b{re.escape(name)}\b",
                haystack,
            ):
                return expected_name

    return None


def generate_news_post(article: dict) -> dict:
    client = Groq(api_key=cfg.GROQ_API_KEY)

    ticker = _detect_ticker(article)

    company_name = _detect_company_name(
        article,
        ticker,
    )

    user_prompt = f"""Article headline:
{article.get('headline')}

Article summary:
{article.get('summary')}

Source:
{article.get('source', 'unknown')}

Detected ticker:
{ticker or 'NONE'}

Detected company/asset name:
{company_name or 'NONE'}

Create the Binance Square post using ONLY the article information.

TITLE:

If ticker and company/asset name are available, use EXACTLY this structure:

{company_name or 'Asset'} (${ticker or 'TICKER'}): Hook

Example:

Bitcoin ($BTC): Hits $81K as US bond yields rebound on global oil woes

BODY:

Write exactly 3 short factual paragraphs.

Do NOT create a risk section.

Do NOT add a final ticker line.
The Python program will add it automatically.

If no ticker is detected:
- Do NOT invent one.
- Do NOT create a fake $TICKER.
- Use the company/asset name without a ticker.

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

    post["url"] = article.get("url")
    post["ticker"] = ticker

    return post


def format_news_post(post: dict) -> str:
    """
    Build the final Binance Square post.

    The ticker line is generated by Python, not AI,
    so the final format stays consistent.
    """

    title = post.get("title", "").strip()
    body = post.get("body", "").strip()
    ticker = post.get("ticker")

    parts = []

    if title:
        parts.append(title)

    if body:
        parts.append(body)

    # Force the final ticker line.
    if ticker:
        parts.append(f"**${ticker}**")

    text = "\n\n".join(parts).strip()

    if len(text) > cfg.CHAR_LIMIT:
        text = text[:cfg.CHAR_LIMIT].rstrip()

    return text
