"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.

Rules:
- Only Binance-listed crypto assets are allowed.
- Company-only news is handled: if no valid crypto ticker is found,
  it checks if the news is crypto/Binance-related, and if so,
  assigns a default ticker (BTC) so it won't be dropped.
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
    "binance",
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
    - If no ticker is found, checks if crypto/Binance related,
      assigns default BTC ticker if relevant instead of skipping.
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
        print("[news] Binance symbol list unavailable.")
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

        # যদি সরাসরি টিকার না পাওয়া যায়, তবে ক্রিপ্টো/বিন্যান্স রিলেটেড কিনা চেক করব
        if not ticker:
            full_text_check = f"{headline} {summary}".lower()
            
            if any(word in full_text_check for word in CRYPTO_CONTEXT_WORDS):
                ticker = "BTC"  # ডিফল্ট টিকার হিসেবে BTC অ্যাসাইন করা হলো
                print(
                    f"[news] No direct ticker, but crypto/binance-related. "
                    f"Assigning default ticker: ${ticker} — {headline}"
                )
            else:
                print(
                    f"[news] SKIP — no verified Binance crypto or relevant context: "
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
        
        # ইমেজ ইউআরএল ক্যাপচার করা (যদি news_fetch থেকে আসে)
        article["image_url"] = (
            article.get("image_url") 
            or article.get("urlToImage") 
            or article.get("image")
        )

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

    # 1. Explicit $TICKER
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

    # 2. Full crypto asset names in HEADLINE
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

    # 3. Trading pair in HEADLINE
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

    # 4. Known ticker in HEADLINE
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

    # 5. Finnhub related field
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
        if re.search(
            rf"\b{re.escape(ticker)}\b",
            headline_upper,
        ):
            return ticker

    # 6. Full asset names anywhere
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

    # 7. Standalone Binance ticker
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
        if len(ticker) < 2:
            continue
        if ticker in COMMON_WORD_TICKERS:
            continue
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

    title = (
        f"{asset_name} (${ticker}): "
        f"{headline}"
    )

    if len(title) > 180:
        title = title[:177].rstrip() + "..."

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
        "image_url": article.get("image_url"),
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

    expected_marker = f"(${ticker})"

    if expected_marker.upper() not in title.upper():
        raise RuntimeError(
            f"AI title does not contain verified "
            f"ticker ${ticker}: {title}"
        )

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

    ticker = article.get("ticker")

    if not ticker:
        ticker = _detect_ticker(article)

    if not ticker:
        ticker = "BTC"  # সেফটি ফলব্যাক হিসেবে BTC

    ticker = ticker.upper().strip()

    if not is_binance_crypto_ticker(ticker):
        raise RuntimeError(
            f"Article rejected: ${ticker} is not currently "
            "verified as a Binance Spot crypto asset."
        )

    asset_name = _detect_asset_name(ticker)

    if not asset_name:
        raise RuntimeError(
            f"Article rejected: unable to identify "
            f"crypto asset ${ticker}."
        )

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
            post = json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise RuntimeError(
                f"Model did not return valid JSON: {raw}"
            ) from err

        post = _validate_generated_post(
            post,
            ticker,
        )

        post["url"] = article.get("url")
        post["ticker"] = ticker
        post["image_url"] = article.get("image_url")

        print(
            f"[news_post_generator] Groq post "
            f"generated successfully for ${ticker}."
        )

        return post

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

    ticker = post.get("ticker")

    if not ticker:
        raise RuntimeError(
            "Refusing to publish: no crypto ticker."
        )

    ticker = str(
        ticker
    ).upper().strip()

    body = re.sub(
        rf"\n*\*\*\s*\${re.escape(ticker)}\s*\*\*\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()

    parts = []

    if title:
        parts.append(title)

    if body:
        parts.append(body)

    parts.append(
        f"**${ticker}**"
    )

    text = "\n\n".join(
        parts
    ).strip()

    if len(text) > cfg.CHAR_LIMIT:
        text = (
            text[:cfg.CHAR_LIMIT]
            .rstrip()
        )

    return text
