"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

Rules:
- Only Binance-listed crypto assets are allowed.
- Company-only/general news is rejected when no reliable
  crypto ticker is found.
- Articles already posted are rejected.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- AI cannot invent or change the verified ticker.
- Standalone English words are NOT accepted as tickers.
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


# =========================================================
# GROQ SYSTEM PROMPT
# =========================================================

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


# =========================================================
# CRYPTO NAME → TICKER
# =========================================================

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


# =========================================================
# TICKER → READABLE NAME
# =========================================================

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


# =========================================================
# COMMON ENGLISH WORDS
#
# These are NEVER accepted as standalone tickers.
# =========================================================

COMMON_WORD_TICKERS = {
    "THE",
    "AND",
    "FOR",
    "ARE",
    "NOT",
    "BUT",
    "CAN",
    "ONE",
    "ALL",
    "ANY",
    "NEW",
    "NOW",
    "LOW",
    "HIGH",
    "TOP",
    "USE",
    "GET",
    "GOT",
    "HAS",
    "HAD",
    "HIS",
    "HER",
    "OUR",
    "OUT",
    "YOU",
    "YOUR",
    "ITS",
    "IN",
    "ON",
    "OR",
    "AS",
    "AT",
    "BY",
    "TO",
    "OF",
    "IT",
    "IS",
    "BE",
    "WE",
    "HE",
    "SHE",
    "DO",
    "GO",
    "NO",
    "SO",
    "UP",
    "DOWN",
    "AR",
    "OP",
    "AI",
    "ME",
    "MY",
    "US",
    "IF",
    "THAN",
    "THEN",
    "THIS",
    "THAT",
    "THEIR",
    "THEM",
    "WITH",
    "FROM",
    "OVER",
    "UNDER",
    "MORE",
    "MOST",
    "JUST",
    "BACK",
    "NEXT",
    "LAST",
    "FIRST",
    "STILL",
    "EVEN",
    "ONLY",
    "MAY",
    "MUST",
    "WILL",
    "WOULD",
    "COULD",
    "SHOULD",

    # Common words that have caused false detections
    "BANK",
    "HOME",
    "NEWS",
    "MARKET",
    "WORLD",
    "GLOBAL",
    "STATE",
    "STATES",
    "UNITED",
    "GROUP",
    "MEDIA",
    "DATA",
    "SYSTEM",
    "SYSTEMS",
    "NETWORK",
    "TECH",
    "TECHNOLOGY",
    "DIGITAL",
    "CAPITAL",
    "POWER",
    "ENERGY",
    "CASH",
    "MONEY",
    "TRADE",
    "TRADING",
    "FINANCE",
    "FINANCIAL",
    "POLICY",
    "POLICIES",
    "LAW",
    "LEGAL",
    "SEC",
    "ETF",
    "ETFS",
    "CEO",
    "FUND",
    "FUNDS",
    "INDEX",
    "STOCK",
    "STOCKS",
    "SHARE",
    "SHARES",
    "VALUE",
    "PRICE",
    "PRICES",
    "RISK",
    "PLAN",
    "PLANS",
    "ACT",
    "ACTION",
    "CHANGE",
    "CHANGES",
    "PUBLIC",
    "PRIVATE",
    "PEOPLE",
    "COMPANY",
    "COMPANIES",
}


# =========================================================
# CRYPTO CONTEXT WORDS
# =========================================================

CRYPTO_CONTEXT_WORDS = (
    "crypto",
    "cryptocurrency",
    "cryptocurrencies",
    "token",
    "tokens",
    "coin",
    "coins",
    "blockchain",
    "network",
    "protocol",
    "defi",
    "stablecoin",
    "stablecoins",
    "wallet",
    "exchange",
    "onchain",
    "on-chain",
    "web3",
    "layer",
    "mainnet",
    "testnet",
    "dao",
    "staking",
    "ecosystem",
    "altcoin",
    "altcoins",
    "digital asset",
    "digital assets",
)


# =========================================================
# HELPERS
# =========================================================

def _contains_crypto_context(
    text: str,
) -> bool:
    """
    Check whether the text contains an explicit
    crypto-related context word.
    """

    if not text:
        return False

    lower_text = text.lower()

    return any(
        word in lower_text
        for word in CRYPTO_CONTEXT_WORDS
    )


def _is_valid_binance_ticker(
    ticker: str,
    binance_tickers: set[str],
) -> bool:
    """
    Strict Binance ticker validation.

    A ticker must:
    - exist in current Binance Spot assets
    - not be a known common English word
    """

    if not ticker:
        return False

    ticker = (
        str(ticker)
        .upper()
        .strip()
        .replace("$", "")
    )

    if not ticker:
        return False

    if ticker in COMMON_WORD_TICKERS:
        return False

    if ticker not in binance_tickers:
        return False

    return True


# =========================================================
# CANDIDATE ARTICLE
# =========================================================

def get_candidate_article(
    seen_urls: set,
    blocked_tickers: set | None = None,
) -> dict | None:
    """
    Return ONE eligible crypto article.

    Rules:
    - Already-posted article URL is skipped.
    - Already-posted ticker for today is skipped.
    - Articles without a reliable crypto ticker are skipped.
    - Ticker must be currently listed on Binance Spot.
    """

    if blocked_tickers is None:
        blocked_tickers = set()

    blocked_tickers = {
        str(t).upper().strip()
        for t in blocked_tickers
        if t
    }

    articles = fetch_crypto_news()

    if not articles:

        print(
            "[news] news source returned "
            "no articles."
        )

        return None

    candidates = []

    # ---------------------------------------------------------
    # Current Binance Spot tickers
    # ---------------------------------------------------------

    binance_tickers = (
        get_binance_crypto_tickers()
    )

    if not binance_tickers:

        print(
            "[news] Binance symbol list unavailable."
        )

        return None

    # ---------------------------------------------------------
    # Process articles
    # ---------------------------------------------------------

    for article in articles:

        if not isinstance(
            article,
            dict,
        ):
            continue

        url = str(
            article.get(
                "url",
                "",
            )
            or ""
        ).strip()

        headline = str(
            article.get(
                "headline",
                "",
            )
            or ""
        ).strip()

        summary = str(
            article.get(
                "summary",
                "",
            )
            or ""
        ).strip()

        # -----------------------------------------------------
        # Basic validation
        # -----------------------------------------------------

        if not url:
            continue

        if url in seen_urls:

            print(
                "[news] SKIP — article already posted: "
                f"{headline}"
            )

            continue

        if not headline:
            continue

        # -----------------------------------------------------
        # Detect ticker
        # -----------------------------------------------------

        ticker = _detect_ticker(
            article,
            binance_tickers,
        )

        if not ticker:

            print(
                "[news] SKIP — no reliable Binance "
                f"crypto ticker: {headline}"
            )

            continue

        ticker = (
            ticker
            .upper()
            .strip()
        )

        # -----------------------------------------------------
        # Daily ticker block
        # -----------------------------------------------------

        if ticker in blocked_tickers:

            print(
                f"[news] SKIP — ${ticker} already "
                f"posted today: {headline}"
            )

            continue

        # -----------------------------------------------------
        # Save verified ticker
        # -----------------------------------------------------

        article["ticker"] = ticker

        candidates.append(
            article
        )

    # ---------------------------------------------------------
    # No candidates
    # ---------------------------------------------------------

    if not candidates:

        print(
            "[news] no eligible crypto article found "
            "after Binance + article history + "
            "daily ticker filters."
        )

        return None

    # ---------------------------------------------------------
    # Recent candidate pool
    # ---------------------------------------------------------

    pool = candidates[:10]

    article = random.choice(
        pool
    )

    print(
        "[news] selected crypto article: "
        f"${article.get('ticker')} — "
        f"{article.get('headline')}"
    )

    return article


# =========================================================
# TICKER DETECTION
# =========================================================

def _detect_ticker(
    article: dict,
    binance_tickers: set[str] | None = None,
) -> str | None:
    """
    Detect a crypto ticker safely.

    Priority:

    1. Explicit $TICKER
    2. Finnhub related ticker
    3. Trading-pair format
    4. Full known crypto asset name

    IMPORTANT:
    We intentionally DO NOT scan every Binance ticker
    as a standalone English word.

    This prevents false detections such as:
        BANK
        HOME
        CYBER
        ACT
        etc.
    """

    if binance_tickers is None:

        binance_tickers = (
            get_binance_crypto_tickers()
        )

    if not binance_tickers:

        return None

    headline = str(
        article.get(
            "headline",
            "",
        )
        or ""
    )

    summary = str(
        article.get(
            "summary",
            "",
        )
        or ""
    )

    haystack = (
        f"{headline} {summary}"
    )

    upper_text = haystack.upper()

    # =========================================================
    # 1. EXPLICIT $TICKER
    # =========================================================

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        upper_text,
    )

    for ticker in explicit_tickers:

        ticker = ticker.upper()

        if _is_valid_binance_ticker(
            ticker,
            binance_tickers,
        ):

            return ticker

    # =========================================================
    # 2. FINNHUB "RELATED"
    # =========================================================

    related = article.get(
        "related",
        "",
    )

    if isinstance(
        related,
        str,
    ):

        related_items = re.split(
            r"[,;|\s]+",
            related,
        )

        for item in related_items:

            ticker = (
                str(item)
                .strip()
                .upper()
            )

            if _is_valid_binance_ticker(
                ticker,
                binance_tickers,
            ):

                return ticker

    elif isinstance(
        related,
        list,
    ):

        for item in related:

            ticker = (
                str(item)
                .strip()
                .upper()
            )

            if _is_valid_binance_ticker(
                ticker,
                binance_tickers,
            ):

                return ticker

    # =========================================================
    # 3. TRADING PAIR
    # =========================================================

    pair_matches = re.findall(
        r"\b([A-Z][A-Z0-9]{1,14})\s*[/\-]\s*"
        r"(USDT|USDC|USD|BTC|ETH|BNB)\b",
        upper_text,
    )

    for ticker, quote in pair_matches:

        ticker = ticker.upper()

        if _is_valid_binance_ticker(
            ticker,
            binance_tickers,
        ):

            return ticker

    # =========================================================
    # 4. FULL CRYPTO ASSET NAME
    # =========================================================

    for name in sorted(
        ASSET_NAME_MAP,
        key=len,
        reverse=True,
    ):

        if not re.search(
            rf"\b{re.escape(name)}\b",
            upper_text,
        ):
            continue

        ticker = (
            ASSET_NAME_MAP[name]
        )

        if _is_valid_binance_ticker(
            ticker,
            binance_tickers,
        ):

            return ticker

    # =========================================================
    # IMPORTANT
    # =========================================================
    #
    # No standalone Binance ticker detection.
    #
    # Example:
    #
    # "Bank of Korea launches..."
    #
    # BANK may exist as a Binance ticker, but the article
    # does not explicitly identify BANK as a crypto asset.
    #
    # Therefore it is rejected.
    #
    # =========================================================

    return None


# =========================================================
# ASSET NAME
# =========================================================

def _detect_asset_name(
    ticker: str,
) -> str | None:
    """
    Return a readable crypto asset name.

    For assets not included in the small known-name map,
    the verified ticker is used as the display name.
    """

    if not ticker:

        return None

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    return KNOWN_ASSET_NAMES.get(
        ticker,
        ticker,
    )


# =========================================================
# GENERATE NEWS POST
# =========================================================

def generate_news_post(
    article: dict,
) -> dict:
    """
    Generate a Binance Square post ONLY for a verified
    Binance-listed crypto asset.
    """

    # ---------------------------------------------------------
    # Get verified ticker from candidate selector
    # ---------------------------------------------------------

    ticker = article.get(
        "ticker"
    )

    if not ticker:

        ticker = _detect_ticker(
            article
        )

    if not ticker:

        raise RuntimeError(
            "Article rejected: no reliable "
            "Binance-listed crypto ticker detected."
        )

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    # ---------------------------------------------------------
    # Verify against Binance again
    # ---------------------------------------------------------

    if not is_binance_crypto_ticker(
        ticker
    ):

        raise RuntimeError(
            f"Article rejected: ${ticker} is not "
            "currently verified as a Binance Spot "
            "crypto asset."
        )

    # ---------------------------------------------------------
    # Get readable asset name
    # ---------------------------------------------------------

    asset_name = _detect_asset_name(
        ticker
    )

    if not asset_name:

        raise RuntimeError(
            f"Article rejected: unable to identify "
            f"crypto asset ${ticker}."
        )

    # ---------------------------------------------------------
    # Groq client
    # ---------------------------------------------------------

    if not cfg.GROQ_API_KEY:

        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    client = Groq(
        api_key=cfg.GROQ_API_KEY
    )

    # ---------------------------------------------------------
    # Prompt
    # ---------------------------------------------------------

    user_prompt = f"""Article headline:
{article.get('headline', '')}

Article summary:
{article.get('summary', '')}

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
        completion.choices[0]
        .message
        .content
        or ""
    )

    # ---------------------------------------------------------
    # Clean response
    # ---------------------------------------------------------

    cleaned = (
        raw
        .replace(
            "```json",
            "",
        )
        .replace(
            "```",
            "",
        )
        .strip()
    )

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    try:

        post = json.loads(
            cleaned
        )

    except json.JSONDecodeError as err:

        raise RuntimeError(
            "Model did not return valid JSON: "
            f"{raw}"
        ) from err

    # ---------------------------------------------------------
    # Validate response object
    # ---------------------------------------------------------

    if not isinstance(
        post,
        dict,
    ):

        raise RuntimeError(
            "AI returned an invalid JSON object."
        )

    title = str(
        post.get(
            "title",
            "",
        )
        or ""
    ).strip()

    body = str(
        post.get(
            "body",
            "",
        )
        or ""
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
                "AI used wrong ticker in title: "
                f"${title_tickers[0]} "
                f"instead of ${ticker}"
            )

    # ---------------------------------------------------------
    # Require correct ticker marker
    # ---------------------------------------------------------

    expected_marker = (
        f"(${ticker})"
    )

    if expected_marker not in title.upper():

        raise RuntimeError(
            "AI title does not contain verified "
            f"ticker ${ticker}: {title}"
        )

    # ---------------------------------------------------------
    # Save final post
    # ---------------------------------------------------------

    post["title"] = title

    post["body"] = body

    post["url"] = article.get(
        "url"
    )

    post["ticker"] = ticker

    return post


# =========================================================
# FORMAT FINAL POST
# =========================================================

def format_news_post(
    post: dict,
) -> str:
    """
    Build final Binance Square post.

    Python generates the final ticker line.
    """

    title = str(
        post.get(
            "title",
            "",
        )
        or ""
    ).strip()

    body = str(
        post.get(
            "body",
            "",
        )
        or ""
    ).strip()

    ticker = post.get(
        "ticker"
    )

    if not ticker:

        raise RuntimeError(
            "Refusing to publish: no crypto ticker."
        )

    ticker = (
        str(ticker)
        .upper()
        .strip()
    )

    parts = []

    if title:

        parts.append(
            title
        )

    if body:

        parts.append(
            body
        )

    # ---------------------------------------------------------
    # Final ticker line
    # ---------------------------------------------------------

    parts.append(
        f"**${ticker}**"
    )

    text = "\n\n".join(
        parts
    ).strip()

    # ---------------------------------------------------------
    # Character limit
    # ---------------------------------------------------------

    if len(text) > cfg.CHAR_LIMIT:

        text = (
            text[:cfg.CHAR_LIMIT]
            .rstrip()
        )

    return text
