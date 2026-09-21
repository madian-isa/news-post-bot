"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

Rules:
- Only Binance-listed crypto assets are allowed.
- Company-only news is rejected when no valid crypto ticker is found.
- Articles already posted are rejected.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- AI cannot invent or change the verified ticker.
- Groq is used directly through the OpenAI-compatible API.
"""

from __future__ import annotations

import json
import os
import random
import re

import requests

import config as cfg
from news_fetch import fetch_crypto_news
from binance_symbols import (
    get_binance_crypto_tickers,
    is_binance_crypto_ticker,
)


# =============================================================
# GROQ
# =============================================================

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _get_groq_api_key() -> str | None:
    """
    Get Groq API key.

    Priority:
    1. config.py
    2. GROQ_API_KEY environment variable
    """

    key = getattr(cfg, "GROQ_API_KEY", None)

    if key:
        key = str(key).strip()

    if not key:
        key = os.environ.get(
            "GROQ_API_KEY",
            "",
        ).strip()

    if not key:
        print(
            "[news_post_generator] ERROR: "
            "GROQ_API_KEY is not set."
        )
        return None

    return key


# =============================================================
# SYSTEM PROMPT
# =============================================================

SYSTEM_PROMPT = """
You are a professional crypto news writer for Binance Square.

Your job is to turn ONE real crypto-asset news article into a
short, natural, factual Binance Square post.

IMPORTANT:

Python has already verified the crypto ticker.

You MUST write ONLY about that verified crypto asset.

Do NOT identify another crypto asset yourself.

Do NOT change the ticker.

Do NOT invent a ticker.

Do NOT invent facts.

Use ONLY information contained in the supplied article
headline and article content/summary.

STYLE:

- Professional
- Natural
- Human-like
- Concise
- News/research style
- Sharp but not sensational
- Suitable for Binance Square

FORMAT:

Title

Paragraph 1.

Paragraph 2.

Paragraph 3.

STRICT RULES:

- Exactly 3 short paragraphs.
- Body should normally be around 100-140 words.
- Title must follow:

Coin Name ($TICKER): Hook

- Title must NOT be all caps.
- Do NOT use emojis.
- Do NOT use hashtags.
- Do NOT use bullet points.
- Do NOT use a separate risk section.
- Do NOT use buy/sell language.
- Do NOT use long/short language.
- Do NOT use target/entry/SL/TP language.
- Do NOT give investment advice.
- Do NOT make unsupported price predictions.
- Do NOT invent statistics.
- Do NOT invent dates.
- Do NOT invent partnerships.
- Do NOT invent quotes.
- Do NOT invent events.
- Do NOT add information from your own knowledge.
- Do NOT add a final ticker line.
- The Python program will add the final ticker line.

Return ONLY valid JSON.

Return exactly:

{
  "title": "string",
  "body": "string"
}
"""


# =============================================================
# ASSET NAME → TICKER
# =============================================================

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
    "MORPHO": "MORPHO",
}


# =============================================================
# KNOWN READABLE NAMES
# =============================================================

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
    "MORPHO": "Morpho",
}


# =============================================================
# COMMON ENGLISH WORDS
# =============================================================

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
}


# =============================================================
# CRYPTO CONTEXT
# =============================================================

CRYPTO_CONTEXT_WORDS = (
    "crypto",
    "cryptocurrency",
    "token",
    "tokens",
    "coin",
    "coins",
    "blockchain",
    "network",
    "protocol",
    "defi",
    "stablecoin",
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
    "smart contract",
    "liquidity",
    "validator",
    "validators",
)


# =============================================================
# ARTICLE TEXT HELPERS
# =============================================================

def _get_article_title(article: dict) -> str:
    """
    Support different news_fetch.py field names.
    """

    return str(
        article.get("headline")
        or article.get("title")
        or ""
    ).strip()


def _get_article_content(article: dict) -> str:
    """
    Support different news_fetch.py field names.
    """

    content = (
        article.get("summary")
        or article.get("content")
        or article.get("description")
        or ""
    )

    return str(content).strip()


# =============================================================
# FIND CANDIDATE ARTICLE
# =============================================================

def get_candidate_article(
    seen_urls: set,
    blocked_tickers: set | None = None,
) -> dict | None:
    """
    Return ONE eligible crypto article.

    Filters:

    1. Article must have URL.
    2. Article must not already be posted.
    3. Article must contain a verified Binance crypto ticker.
    4. Same ticker must not already be posted today.
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
            "[news] No crypto news articles returned."
        )
        return None

    candidates = []

    # ---------------------------------------------------------
    # Binance-listed crypto tickers
    # ---------------------------------------------------------

    binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:
        print(
            "[news] Binance symbol list unavailable."
        )
        return None

    binance_tickers = {
        str(t).upper().strip()
        for t in binance_tickers
        if t
    }

    print(
        f"[news] Binance crypto tickers loaded: "
        f"{len(binance_tickers)}"
    )

    # ---------------------------------------------------------
    # Process articles
    # ---------------------------------------------------------

    for article in articles:

        url = str(
            article.get("url")
            or ""
        ).strip()

        headline = _get_article_title(
            article
        )

        if not url:
            continue

        if not headline:
            continue

        # -----------------------------------------------------
        # Already posted article
        # -----------------------------------------------------

        if url in seen_urls:

            print(
                f"[news] SKIP — article already posted: "
                f"{headline}"
            )

            continue

        # -----------------------------------------------------
        # Detect verified ticker
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

        ticker = ticker.upper().strip()

        # -----------------------------------------------------
        # Daily ticker block
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

        candidates.append(
            article
        )

    # ---------------------------------------------------------
    # No candidates
    # ---------------------------------------------------------

    if not candidates:

        print(
            "[news] No eligible crypto article found "
            "after Binance + article history + "
            "daily ticker filters."
        )

        return None

    # ---------------------------------------------------------
    # Recent pool
    # ---------------------------------------------------------

    pool = candidates[:10]

    article = random.choice(
        pool
    )

    print(
        f"[news] Selected crypto article: "
        f"${article.get('ticker')} — "
        f"{_get_article_title(article)}"
    )

    return article


# =============================================================
# TICKER DETECTION
# =============================================================

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
    4. Known crypto asset name
    5. Binance-listed standalone ticker
    """

    if binance_tickers is None:
        binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:
        return None

    headline = _get_article_title(
        article
    )

    summary = _get_article_content(
        article
    )

    haystack = f"{headline} {summary}"

    upper_text = haystack.upper()
    lower_text = haystack.lower()

    # =========================================================
    # 1. Explicit $TICKER
    # =========================================================

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        upper_text,
    )

    for ticker in explicit_tickers:

        ticker = ticker.upper()

        if ticker in binance_tickers:

            return ticker

    # =========================================================
    # 2. Finnhub "related"
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

            ticker = item.strip().upper()

            if (
                ticker
                and ticker in binance_tickers
                and ticker not in COMMON_WORD_TICKERS
            ):

                return ticker

    elif isinstance(
        related,
        list,
    ):

        for item in related:

            ticker = str(
                item
            ).strip().upper()

            if (
                ticker
                and ticker in binance_tickers
                and ticker not in COMMON_WORD_TICKERS
            ):

                return ticker

    # =========================================================
    # 3. Trading pair
    # =========================================================

    pair_matches = re.findall(
        r"\b([A-Z][A-Z0-9]{1,14})\s*[/\-]\s*"
        r"(USDT|USDC|USD|BTC|ETH|BNB)\b",
        upper_text,
    )

    for ticker, quote in pair_matches:

        ticker = ticker.upper()

        if (
            ticker in binance_tickers
            and ticker not in COMMON_WORD_TICKERS
        ):

            return ticker

    # =========================================================
    # 4. Full crypto asset name
    # =========================================================

    for name in sorted(
        ASSET_NAME_MAP,
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(name)}\b",
            upper_text,
        ):

            ticker = ASSET_NAME_MAP[name]

            if ticker in binance_tickers:

                return ticker

    # =========================================================
    # 5. Standalone Binance ticker
    # =========================================================

    has_crypto_context = any(
        word in lower_text
        for word in CRYPTO_CONTEXT_WORDS
    )

    if not has_crypto_context:
        return None

    possible_tickers = sorted(
        binance_tickers,
        key=len,
        reverse=True,
    )

    for ticker in possible_tickers:

        ticker = ticker.upper()

        if len(ticker) < 2:
            continue

        if ticker in COMMON_WORD_TICKERS:
            continue

        if re.search(
            rf"\b{re.escape(ticker)}\b",
            upper_text,
        ):

            return ticker

    return None


# =============================================================
# ASSET NAME
# =============================================================

def _detect_asset_name(
    ticker: str,
) -> str | None:
    """
    Return readable crypto asset name.

    Known assets use readable names.

    Unknown Binance-listed assets fall back
    to their ticker instead of inventing a name.
    """

    if not ticker:
        return None

    ticker = str(
        ticker
    ).upper().strip()

    return KNOWN_ASSET_NAMES.get(
        ticker,
        ticker,
    )


# =============================================================
# GENERATE NEWS POST
# =============================================================

def generate_news_post(
    article: dict,
) -> dict | None:
    """
    Generate a Binance Square post ONLY for a verified
    Binance-listed crypto asset.
    """

    # =========================================================
    # Get verified ticker
    # =========================================================

    ticker = article.get(
        "ticker"
    )

    if not ticker:

        ticker = _detect_ticker(
            article
        )

    if not ticker:

        raise RuntimeError(
            "Article rejected: no Binance-listed crypto "
            "ticker detected."
        )

    ticker = str(
        ticker
    ).upper().replace(
        "$",
        "",
    ).strip()

    # =========================================================
    # Verify AGAIN against Binance
    # =========================================================

    if not is_binance_crypto_ticker(
        ticker
    ):

        raise RuntimeError(
            f"Article rejected: ${ticker} is not currently "
            "verified as a Binance Spot crypto asset."
        )

    # =========================================================
    # Asset name
    # =========================================================

    asset_name = _detect_asset_name(
        ticker
    )

    if not asset_name:

        raise RuntimeError(
            f"Article rejected: unable to identify "
            f"crypto asset ${ticker}."
        )

    # =========================================================
    # Groq API key
    # =========================================================

    api_key = _get_groq_api_key()

    if not api_key:
        return None

    # =========================================================
    # Article data
    # =========================================================

    headline = _get_article_title(
        article
    )

    content = _get_article_content(
        article
    )

    source = str(
        article.get(
            "source",
            "unknown",
        )
    ).strip()

    if not headline:

        raise RuntimeError(
            "Article rejected: missing headline."
        )

    if not content:
        content = headline

    # =========================================================
    # User prompt
    # =========================================================

    user_prompt = f"""
Create a Binance Square crypto news post.

VERIFIED CRYPTO ASSET:
{asset_name}

VERIFIED TICKER:
${ticker}

ARTICLE HEADLINE:
{headline}

ARTICLE CONTENT:
{content}

SOURCE:
{source}

IMPORTANT:

The article is already verified by Python as being related to:

{asset_name} (${ticker})

Write ONLY about this asset.

Do not change the ticker.

TITLE:

Use exactly:

{asset_name} (${ticker}): Hook

The Hook should be attention-grabbing but factual.

BODY:

Write exactly 3 short paragraphs.

Use ONLY information from the supplied headline and article
content.

The post should explain:

1. What happened.
2. The key development or detail.
3. Why the development matters based only on the article.

Do NOT add:
- hashtags
- emojis
- bullet points
- investment advice
- buy/sell language
- long/short language
- target language
- entry language
- stop-loss language
- take-profit language
- unsupported predictions
- invented statistics
- invented events
- invented quotes
- information from outside knowledge

Do NOT add a final **${ticker}** line.

Python will add it.

Return ONLY valid JSON:

{{
  "title": "string",
  "body": "string"
}}
"""

    # =========================================================
    # Request
    # =========================================================

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": getattr(
            cfg,
            "GROQ_MODEL",
            "llama-3.3-70b-versatile",
        ),
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "temperature": 0.5,
        "max_tokens": 400,
    }

    try:

        print(
            f"[news_post_generator] "
            f"Generating post for ${ticker} via Groq API..."
        )

        response = requests.post(
            GROQ_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        raw = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not raw:

            raise RuntimeError(
                "Groq returned an empty response."
            )

        # =====================================================
        # Clean markdown fences
        # =====================================================

        cleaned = raw.strip()

        if cleaned.startswith(
            "```json"
        ):

            cleaned = cleaned[
                7:
            ].strip()

        elif cleaned.startswith(
            "```"
        ):

            cleaned = cleaned[
                3:
            ].strip()

        if cleaned.endswith(
            "```"
        ):

            cleaned = cleaned[
                :-3
            ].strip()

        # =====================================================
        # Parse JSON
        # =====================================================

        try:

            post = json.loads(
                cleaned
            )

        except json.JSONDecodeError as err:

            raise RuntimeError(
                "Groq did not return valid JSON: "
                f"{raw}"
            ) from err

        # =====================================================
        # Validate fields
        # =====================================================

        title = str(
            post.get(
                "title",
                "",
            )
        ).strip()

        body = str(
            post.get(
                "body",
                "",
            )
        ).strip()

        if not title:

            raise RuntimeError(
                "AI returned an empty title."
            )

        if not body:

            raise RuntimeError(
                "AI returned an empty body."
            )

        # =====================================================
        # Validate ticker
        # =====================================================

        title_tickers = re.findall(
            r"\$([A-Z][A-Z0-9]{1,14})\b",
            title.upper(),
        )

        if not title_tickers:

            raise RuntimeError(
                f"AI title is missing verified ticker "
                f"${ticker}: {title}"
            )

        if title_tickers[0] != ticker:

            raise RuntimeError(
                f"AI used wrong ticker in title: "
                f"${title_tickers[0]} "
                f"instead of ${ticker}"
            )

        # =====================================================
        # Exact marker validation
        # =====================================================

        expected_marker = (
            f"(${ticker})"
        )

        if expected_marker not in title.upper():

            raise RuntimeError(
                f"AI title does not contain verified "
                f"ticker ${ticker}: {title}"
            )

        # =====================================================
        # Prevent AI from adding another ticker
        # =====================================================

        body_tickers = re.findall(
            r"\$([A-Z][A-Z0-9]{1,14})\b",
            body.upper(),
        )

        for body_ticker in body_tickers:

            if body_ticker != ticker:

                raise RuntimeError(
                    f"AI introduced another ticker "
                    f"${body_ticker} in body. "
                    f"Expected only ${ticker}."
                )

        # =====================================================
        # Basic forbidden-language validation
        # =====================================================

        combined_text = (
            f"{title}\n{body}"
        ).lower()

        forbidden_patterns = [
            r"#\w+",
            r"\bbuy\b",
            r"\bsell\b",
            r"\blong\b",
            r"\bshort\b",
            r"\bentry\b",
            r"\bstop[\s-]?loss\b",
            r"\btake[\s-]?profit\b",
        ]

        for pattern in forbidden_patterns:

            if re.search(
                pattern,
                combined_text,
            ):

                raise RuntimeError(
                    "AI output contains forbidden "
                    f"content matching: {pattern}"
                )

        # =====================================================
        # Save final post
        # =====================================================

        post["title"] = title
        post["body"] = body
        post["url"] = article.get(
            "url"
        )
        post["ticker"] = ticker

        print(
            f"[news_post_generator] "
            f"Successfully generated post "
            f"({len(body)} body chars)."
        )

        return post

    except requests.RequestException as err:

        print(
            "[news_post_generator] "
            f"Groq API request failed: {err}"
        )

        return None

    except Exception as err:

        print(
            "[news_post_generator] "
            f"Failed to generate post: {err}"
        )

        raise


# =============================================================
# FINAL BINANCE SQUARE FORMAT
# =============================================================

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
    ).strip()

    body = str(
        post.get(
            "body",
            "",
        )
    ).strip()

    ticker = post.get(
        "ticker"
    )

    if not ticker:

        raise RuntimeError(
            "Refusing to publish: no crypto ticker."
        )

    ticker = str(
        ticker
    ).upper().replace(
        "$",
        "",
    ).strip()

    # =========================================================
    # Final verification
    # =========================================================

    if not is_binance_crypto_ticker(
        ticker
    ):

        raise RuntimeError(
            f"Refusing to publish: ${ticker} "
            "is not a verified Binance crypto ticker."
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

    # =========================================================
    # Python-controlled ticker line
    # =========================================================

    parts.append(
        f"**${ticker}**"
    )

    text = "\n\n".join(
        parts
    ).strip()

    # =========================================================
    # Character limit
    # =========================================================

    char_limit = int(
        getattr(
            cfg,
            "CHAR_LIMIT",
            2000,
        )
    )

    if len(text) > char_limit:

        text = (
            text[:char_limit]
            .rstrip()
        )

    return text
