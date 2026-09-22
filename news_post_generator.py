"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

Rules:
- Only Binance-listed crypto assets are allowed.
- Company-only news is rejected when no valid crypto ticker is found.
- Articles already posted are rejected.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- AI cannot invent or change the verified ticker.
- If Groq fails, a factual Python fallback is used.
"""

import json
import random
import re

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


# =============================================================
# Crypto name -> ticker
# =============================================================

ASSET_NAME_MAP = {
    "BITCOIN CASH": "BCH",
    "BINANCE COIN": "BNB",
    "DOGECOIN": "DOGE",
    "SHIBA INU": "SHIB",
    "INTERNET COMPUTER": "ICP",
    "NEAR PROTOCOL": "NEAR",
    "WORLDCOIN": "WLD",
    "WORLD": "WLD",
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


# =============================================================
# Ticker -> readable crypto name
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
}


# =============================================================
# Ambiguous/common English words
#
# These should NOT be accepted as standalone tickers.
# =============================================================

COMMON_WORD_TICKERS = {
    "ACT",
    "BANK",
    "HOME",
    "CYBER",
    "LAYER",
    "MEME",
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
# Crypto context words
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
)


# =============================================================
# Utility
# =============================================================

def _clean_text(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _sentence_list(text: str) -> list[str]:
    text = _clean_text(text)

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    return [
        s.strip()
        for s in sentences
        if s.strip()
    ]


def _trim_text(text: str, limit: int = 380) -> str:
    text = _clean_text(text)

    if len(text) <= limit:
        return text

    shortened = text[:limit]

    last_space = shortened.rfind(" ")

    if last_space > 100:
        shortened = shortened[:last_space]

    return shortened.rstrip(" ,;:-") + "."


# =============================================================
# Candidate article selection
# =============================================================

def get_candidate_article(
    seen_urls: set,
    blocked_tickers: set | None = None,
) -> dict | None:

    """
    Return ONE eligible crypto article.

    Rules:
    - Already-posted article URL is skipped.
    - Already-posted ticker for today is skipped.
    - Articles without a valid crypto ticker are skipped.
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

    candidates = []

    binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:

        print(
            "[news] Binance symbol list unavailable."
        )

        return None

    print(
        f"[news] Binance crypto tickers loaded: "
        f"{len(binance_tickers)}"
    )

    for article in articles:

        url = article.get("url")

        headline = _clean_text(
            article.get("headline", "")
        )

        summary = _clean_text(
            article.get("summary", "")
        )

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

        if ticker in blocked_tickers:

            print(
                f"[news] SKIP — ${ticker} already posted today: "
                f"{headline}"
            )

            continue

        article["ticker"] = ticker

        candidates.append(article)

    if not candidates:

        print(
            "[news] no eligible crypto article found "
            "after Binance + article history + "
            "daily ticker filters."
        )

        return None

    pool = candidates[:10]

    article = random.choice(pool)

    print(
        f"[news] selected crypto article: "
        f"${article.get('ticker')} — "
        f"{article.get('headline')}"
    )

    return article


# =============================================================
# Ticker detection
# =============================================================

def _detect_ticker(
    article: dict,
    binance_tickers: set[str] | None = None,
) -> str | None:

    """
    Detect a crypto ticker safely.

    Priority:

    1. Explicit $TICKER
    2. Exact crypto asset name in HEADLINE
    3. Explicit trading pair
    4. Known crypto ticker strongly connected to HEADLINE
    5. Finnhub related ticker ONLY when supported by headline
    6. Standalone ticker with strong safeguards

    Important:
    Common English words such as ACT, BANK, HOME, MEME,
    CYBER and LAYER are never accepted as standalone tickers.
    """

    if binance_tickers is None:
        binance_tickers = get_binance_crypto_tickers()

    if not binance_tickers:
        return None

    binance_tickers = {
        str(t).upper().strip()
        for t in binance_tickers
        if t
    }

    headline = _clean_text(
        article.get("headline", "")
    )

    summary = _clean_text(
        article.get("summary", "")
    )

    headline_upper = headline.upper()
    summary_upper = summary.upper()

    full_text = f"{headline} {summary}"

    lower_text = full_text.lower()

    # ---------------------------------------------------------
    # 1. Explicit $TICKER
    # ---------------------------------------------------------

    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        headline_upper,
    )

    for ticker in explicit_tickers:

        ticker = ticker.upper()

        if (
            ticker in binance_tickers
            and ticker not in COMMON_WORD_TICKERS
        ):
            return ticker

    explicit_summary_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        summary_upper,
    )

    for ticker in explicit_summary_tickers:

        ticker = ticker.upper()

        if (
            ticker in binance_tickers
            and ticker not in COMMON_WORD_TICKERS
        ):
            return ticker

    # ---------------------------------------------------------
    # 2. Full crypto asset names in HEADLINE
    #
    # Headline gets priority over summary.
    # This prevents:
    #
    # NEAR article + Zcash mentioned in summary
    # -> incorrectly becoming ZEC.
    # ---------------------------------------------------------

    for name in sorted(
        ASSET_NAME_MAP,
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(name)}\b",
            headline_upper,
        ):

            ticker = ASSET_NAME_MAP[name]

            if (
                ticker in binance_tickers
                and ticker not in COMMON_WORD_TICKERS
            ):
                return ticker

    # ---------------------------------------------------------
    # 3. Trading pair in HEADLINE
    # ---------------------------------------------------------

    pair_matches = re.findall(
        r"\b([A-Z][A-Z0-9]{1,14})\s*[/\-]\s*"
        r"(USDT|USDC|USD|BTC|ETH|BNB)\b",
        headline_upper,
    )

    for ticker, quote in pair_matches:

        ticker = ticker.upper()

        if (
            ticker in binance_tickers
            and ticker not in COMMON_WORD_TICKERS
        ):
            return ticker

    # Also support forms such as BTCUSDT.
    compact_pair_matches = re.findall(
        r"\b([A-Z][A-Z0-9]{1,14})(USDT|USDC|USD|BTC|ETH|BNB)\b",
        headline_upper,
    )

    for ticker, quote in compact_pair_matches:

        ticker = ticker.upper()

        if (
            ticker in binance_tickers
            and ticker not in COMMON_WORD_TICKERS
        ):
            return ticker

    # ---------------------------------------------------------
    # 4. Known ticker in HEADLINE
    #
    # Only accept if it is a strong recognizable asset.
    # ---------------------------------------------------------

    headline_candidates = []

    for ticker in binance_tickers:

        if len(ticker) < 2:
            continue

        if ticker in COMMON_WORD_TICKERS:
            continue

        if ticker in KNOWN_ASSET_NAMES:

            if re.search(
                rf"\b{re.escape(ticker)}\b",
                headline_upper,
            ):
                headline_candidates.append(ticker)

    if headline_candidates:

        headline_candidates.sort(
            key=len,
            reverse=True,
        )

        return headline_candidates[0]

    # ---------------------------------------------------------
    # 5. Finnhub related field
    #
    # Do NOT blindly trust related.
    #
    # It must also appear in the headline or have an
    # explicit crypto-name match in the headline.
    # ---------------------------------------------------------

    related = article.get(
        "related",
        "",
    )

    related_items = []

    if isinstance(related, str):

        related_items = re.split(
            r"[,;|\s]+",
            related,
        )

    elif isinstance(related, list):

        related_items = [
            str(x)
            for x in related
        ]

    for item in related_items:

        ticker = item.strip().upper()

        if not ticker:
            continue

        if ticker in COMMON_WORD_TICKERS:
            continue

        if ticker not in binance_tickers:
            continue

        # Related ticker must be explicitly visible in headline.
        if re.search(
            rf"\b{re.escape(ticker)}\b",
            headline_upper,
        ):

            return ticker

    # ---------------------------------------------------------
    # 6. Full asset names anywhere
    #
    # Use this only after headline-priority checks.
    # ---------------------------------------------------------

    for name in sorted(
        ASSET_NAME_MAP,
        key=len,
        reverse=True,
    ):

        if re.search(
            rf"\b{re.escape(name)}\b",
            lower_text,
            re.IGNORECASE,
        ):

            ticker = ASSET_NAME_MAP[name]

            if (
                ticker in binance_tickers
                and ticker not in COMMON_WORD_TICKERS
            ):
                return ticker

    # ---------------------------------------------------------
    # 7. Standalone Binance ticker
    #
    # Strong safeguard:
    # ticker must NOT be an ambiguous English word.
    # ---------------------------------------------------------

    has_crypto_context = any(
        word in lower_text
        for word in CRYPTO_CONTEXT_WORDS
    )

    if not has_crypto_context:
        return None

    # Prefer longer tickers.
    possible_tickers = sorted(
        binance_tickers,
        key=len,
        reverse=True,
    )

    for ticker in possible_tickers:

        if len(ticker) < 2:
            continue

        if ticker in COMMON_WORD_TICKERS:
            continue

        # Do not trust very short generic tickers.
        if len(ticker) <= 2 and ticker not in KNOWN_ASSET_NAMES:
            continue

        if re.search(
            rf"\b{re.escape(ticker)}\b",
            headline_upper,
        ):

            return ticker

    return None


# =============================================================
# Asset name
# =============================================================

def _detect_asset_name(
    ticker: str,
) -> str | None:

    if not ticker:
        return None

    ticker = ticker.upper().strip()

    return KNOWN_ASSET_NAMES.get(
        ticker,
        ticker,
    )


# =============================================================
# Python fallback
# =============================================================

def _python_fallback_post(
    article: dict,
    ticker: str,
) -> dict:

    """
    Deterministic fallback used when Groq is unavailable.

    Important:
    This fallback does NOT invent market facts.
    It only uses the supplied headline and summary.
    """

    ticker = ticker.upper().strip()

    asset_name = _detect_asset_name(
        ticker
    ) or ticker

    headline = _clean_text(
        article.get("headline", "")
    )

    summary = _clean_text(
        article.get("summary", "")
    )

    if not headline:
        raise RuntimeError(
            "Fallback failed: article headline is empty."
        )

    # ---------------------------------------------------------
    # Title
    # ---------------------------------------------------------

    title = (
        f"{asset_name} (${ticker}): "
        f"{headline}"
    )

    # Avoid an excessively long title.
    if len(title) > 180:

        title = title[:177].rstrip() + "..."

    # ---------------------------------------------------------
    # Summary sentences
    # ---------------------------------------------------------

    summary_sentences = _sentence_list(
        summary
    )

    headline_sentence = (
        f"The latest report focuses on {asset_name} "
        f"(${ticker}) and the development described in "
        f"the headline."
    )

    if summary_sentences:

        first = _trim_text(
            summary_sentences[0],
            360,
        )

        paragraph_1 = (
            f"{headline}."
            if not headline.endswith((".", "!", "?"))
            else headline
        )

        paragraph_2 = (
            f"According to the report, {first}"
        )

        if len(summary_sentences) > 1:

            second = _trim_text(
                summary_sentences[1],
                360,
            )

            paragraph_3 = second

        else:

            paragraph_3 = headline_sentence

    else:

        paragraph_1 = (
            headline
            if headline.endswith((".", "!", "?"))
            else headline + "."
        )

        paragraph_2 = headline_sentence

        paragraph_3 = (
            f"The report keeps the focus on the "
            f"specific development involving "
            f"{asset_name} (${ticker})."
        )

    body = "\n\n".join(
        [
            paragraph_1,
            paragraph_2,
            paragraph_3,
        ]
    )

    print(
        f"[news_post_generator] Using Python fallback "
        f"for ${ticker}."
    )

    return {
        "title": title,
        "body": body,
        "url": article.get("url"),
        "ticker": ticker,
    }


# =============================================================
# Validate generated post
# =============================================================

def _validate_generated_post(
    post: dict,
    ticker: str,
) -> dict:

    ticker = ticker.upper().strip()

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

    if not title or not body:

        raise RuntimeError(
            "AI returned an empty title or body."
        )

    # ---------------------------------------------------------
    # Check expected ticker marker
    # ---------------------------------------------------------

    expected_marker = f"(${ticker})"

    if expected_marker.upper() not in title.upper():

        raise RuntimeError(
            f"AI title does not contain verified "
            f"ticker ${ticker}: {title}"
        )

    # ---------------------------------------------------------
    # Detect ALL ticker markers in title
    # ---------------------------------------------------------

    title_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,14})\b",
        title.upper(),
    )

    for found_ticker in title_tickers:

        if found_ticker != ticker:

            raise RuntimeError(
                f"AI used wrong ticker in title: "
                f"${found_ticker} instead of ${ticker}"
            )

    # ---------------------------------------------------------
    # Prevent AI from adding another final ticker line
    # ---------------------------------------------------------

    body_without_final = re.sub(
        rf"\*\*\s*\${re.escape(ticker)}\s*\*\*\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()

    post["title"] = title
    post["body"] = body_without_final
    post["ticker"] = ticker

    return post


# =============================================================
# Generate post
# =============================================================

def generate_news_post(
    article: dict,
) -> dict:

    """
    Generate a Binance Square post ONLY for a verified
    Binance-listed crypto asset.

    Groq failure:
        -> Python fallback
    """

    # ---------------------------------------------------------
    # Get verified ticker
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
            "Article rejected: no Binance-listed crypto "
            "ticker detected."
        )

    ticker = ticker.upper().strip()

    # ---------------------------------------------------------
    # Verify against Binance
    # ---------------------------------------------------------

    if not is_binance_crypto_ticker(
        ticker
    ):

        raise RuntimeError(
            f"Article rejected: ${ticker} is not currently "
            "verified as a Binance Spot crypto asset."
        )

    # ---------------------------------------------------------
    # Asset name
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
    # Groq API
    # ---------------------------------------------------------

    try:

        print(
            f"[news_post_generator] Generating post "
            f"for ${ticker} via Groq..."
        )

        client = Groq(
            api_key=cfg.GROQ_API_KEY
        )

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
            .message.content
            or ""
        )

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

        try:

            post = json.loads(
                cleaned
            )

        except json.JSONDecodeError as err:

            raise RuntimeError(
                f"Model did not return valid JSON: {raw}"
            ) from err

        post = _validate_generated_post(
            post,
            ticker,
        )

        post["url"] = article.get(
            "url"
        )

        post["ticker"] = ticker

        print(
            f"[news_post_generator] Groq post "
            f"generated successfully for ${ticker}."
        )

        return post

    # ---------------------------------------------------------
    # Groq failure -> Python fallback
    # ---------------------------------------------------------

    except Exception as groq_error:

        print(
            f"[news_post_generator] Groq failed for "
            f"${ticker}: {groq_error}"
        )

        print(
            f"[news_post_generator] Falling back to "
            f"Python-generated factual post for ${ticker}."
        )

        return _python_fallback_post(
            article,
            ticker,
        )


# =============================================================
# Final formatting
# =============================================================

def format_news_post(
    post: dict,
) -> str:

    """
    Build final Binance Square post.

    Python generates the final ticker line.
    """

    if not post:

        raise RuntimeError(
            "Refusing to publish: empty post."
        )

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
    ).upper().strip()

    # ---------------------------------------------------------
    # Remove accidental final ticker line
    # ---------------------------------------------------------

    body = re.sub(
        rf"\n*\*\*\s*\${re.escape(ticker)}\s*\*\*\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()

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
    # Python-controlled final ticker
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





















"""
main.py

Single-run mode.

Each invocation attempts to publish ONE crypto-news post.

Rules:
- Only Binance-listed crypto assets are allowed.
- Same article URL cannot be posted twice.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- Maximum daily posts are controlled by config.
- Uses a maximum of 1 image:
    1. crypto logo only
- Article images are not used.
- If the crypto logo is unavailable, falls back to text-only.
- If image upload fails, falls back to text-only.
"""

import traceback

import config as cfg

from news_post_generator import (
    get_candidate_article,
    generate_news_post,
    format_news_post,
)

from news_images import (
    prepare_post_images,
    cleanup_images,
)

from square_post import (
    post_text,
    post_with_images,
)

from news_state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
)


def run_once():

    # =========================================================
    # 1. Load state
    # =========================================================

    state = load_state()

    # =========================================================
    # 2. Daily post limit
    # =========================================================

    if not can_post_more_today(state):

        print(
            f"[news] daily cap reached "
            f"({cfg.NEWS_MAX_POSTS_PER_DAY}) "
            "— skipping this run."
        )

        return

    # =========================================================
    # 3. Today's blocked tickers
    # =========================================================

    blocked_tickers = {
        str(t).upper().strip()
        for t in state.get(
            "posted_tickers",
            [],
        )
        if t
    }

    print(
        "[news] today's blocked tickers: "
        f"{sorted(blocked_tickers)}"
    )

    # =========================================================
    # 4. Previously posted article URLs
    # =========================================================

    seen_urls = set(
        state.get(
            "seen_urls",
            [],
        )
    )

    print(
        "[news] checking for new Binance-listed "
        "crypto articles..."
    )

    # =========================================================
    # 5. Find eligible article
    #
    # Same ticker already posted today:
    #     SKIP
    #
    # Same article URL already posted:
    #     SKIP
    #
    # Different ticker + new article:
    #     eligible
    # =========================================================

    article = get_candidate_article(
        seen_urls,
        blocked_tickers,
    )

    if not article:

        print(
            "[news] no eligible crypto article "
            "found this run."
        )

        return

    # =========================================================
    # 6. Verified ticker
    # =========================================================

    ticker = article.get(
        "ticker"
    )

    if not ticker:

        print(
            "[news] selected article has no "
            "verified ticker."
        )

        return

    ticker = str(
        ticker
    ).upper().strip()

    print(
        f"[news] preparing post for ${ticker}"
    )

    image_paths = []

    try:

        # =====================================================
        # 7. Generate post text
        # =====================================================

        post = generate_news_post(
            article
        )

        generated_ticker = str(
            post.get(
                "ticker",
                "",
            )
        ).upper().strip()

        if generated_ticker != ticker:

            raise RuntimeError(
                f"Ticker mismatch: "
                f"expected ${ticker}, "
                f"got ${generated_ticker}"
            )

        text = format_news_post(
            post
        )

        print(
            f"[news] generated post length: "
            f"{len(text)} chars"
        )

        # =====================================================
        # 8. Prepare ONLY crypto logo
        # =====================================================

        try:

            image_paths = prepare_post_images(
                article,
                ticker,
            )

        except Exception as image_prepare_error:

            print(
                "[news] image preparation failed: "
                f"{image_prepare_error}"
            )

            print(
                "[news] continuing with "
                "text-only post."
            )

            image_paths = []

        # Safety: maximum 1 image
        if len(image_paths) > 1:

            print(
                "[news] more than 1 image returned. "
                "Using only the first image."
            )

            image_paths = image_paths[:1]

        print(
            f"[news] images ready: "
            f"{len(image_paths)}"
        )

        for index, image in enumerate(
            image_paths,
            start=1,
        ):

            print(
                f"[news] image {index}: "
                f"{image}"
            )

        # =====================================================
        # 9. DRY RUN
        # =====================================================

        if cfg.DRY_RUN:

            print(
                "\n[DRY RUN] would post:"
            )

            print(
                "-" * 60
            )

            print(text)

            print(
                "-" * 60
            )

            print(
                f"[DRY RUN] crypto: ${ticker}"
            )

            print(
                f"[DRY RUN] source: "
                f"{article.get('url')}"
            )

            print(
                f"[DRY RUN] images: "
                f"{len(image_paths)}"
            )

            for image in image_paths:

                print(
                    f"[DRY RUN] image -> "
                    f"{image}"
                )

            print(
                "[DRY RUN] nothing posted "
                "to Binance Square.\n"
            )

            return

        # =====================================================
        # 10. Publish
        # =====================================================

        if image_paths:

            print(
                f"[news] attempting image post "
                f"with {len(image_paths)} image(s)..."
            )

            try:

                result = post_with_images(
                    text,
                    image_paths,
                )

                print(
                    "[news] image post succeeded."
                )

            except Exception as image_post_error:

                print(
                    "[news] image post failed: "
                    f"{image_post_error}"
                )

                print(
                    "[news] falling back to "
                    "text-only post..."
                )

                result = post_text(
                    text
                )

                print(
                    "[news] text-only fallback "
                    "succeeded."
                )

        else:

            print(
                "[news] no images available — "
                "publishing text-only."
            )

            result = post_text(
                text
            )

        # =====================================================
        # 11. Publication result
        # =====================================================

        if result:

            print(
                f"[news] published -> "
                f"{result} "
                f"(crypto: ${ticker})"
            )

        else:

            print(
                f"[news] published successfully "
                f"(link unavailable) "
                f"(crypto: ${ticker})"
            )

        print(
            f"[news] source: "
            f"{article.get('url')}"
        )

        # =====================================================
        # 12. Save state ONLY after publication
        # =====================================================

        state = record_post(
            state,
            article.get("url"),
            ticker,
        )

        save_state(
            state
        )

        print(
            f"[news] state saved: "
            f"${ticker} blocked for today."
        )

    except Exception as err:

        print(
            f"[news] failed: {err}"
        )

        traceback.print_exc()

    finally:

        # =====================================================
        # 13. Cleanup images
        # =====================================================

        try:

            cleanup_images(
                image_paths
            )

        except Exception as cleanup_error:

            print(
                "[news] image cleanup failed: "
                f"{cleanup_error}"
            )


if __name__ == "__main__":
    run_once()
