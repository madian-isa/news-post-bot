"""
news_post_generator.py

Generates short, factual Binance Square crypto-asset news posts.
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
# Coin Logo Mapping (Official Logos for highlighted coins)
# =============================================================
COIN_LOGOS = {
    "BTC": "https://assets.coingecko.com/coins/images/1/large/bitcoin.png",
    "ETH": "https://assets.coingecko.com/coins/images/279/large/ethereum.png",
    "BNB": "https://assets.coingecko.com/coins/images/825/large/bnb-icon2_2x.png",
    "SOL": "https://assets.coingecko.com/coins/images/4128/large/solana.png",
    "XRP": "https://assets.coingecko.com/coins/images/44/large/xrp-symbol-white-128.png",
    "ADA": "https://assets.coingecko.com/coins/images/975/large/cardano.png",
    "DOGE": "https://assets.coingecko.com/coins/images/5/large/dogecoin.png",
    "AVAX": "https://assets.coingecko.com/coins/images/12559/large/Avalanche_Circle_RedWhite_Trans.png",
    "LINK": "https://assets.coingecko.com/coins/images/877/large/chainlink-new-logo.png",
    "DOT": "https://assets.coingecko.com/coins/images/12171/large/polkadot.png",
    "ARB": "https://assets.coingecko.com/coins/images/16547/large/arbitrum-shield.png",
    "ZEC": "https://assets.coingecko.com/coins/images/486/large/zcash.png",
    "XAU": "https://assets.coingecko.com/coins/images/95/large/gold.png",
}


# =============================================================
# Crypto name -> ticker
# =============================================================

ASSET_NAME_MAP = {
    "BITCOIN CASH": "BCH",
    "BINANCE COIN": "BNB",
    "BNB": "BNB",
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
    "USDC": "USDC",
    "USD COIN": "USDC",
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
    "USDC": "USD Coin",
    "XAU": "Gold",
}


# =============================================================
# Ambiguous / Common English words
# =============================================================

COMMON_WORD_TICKERS = {
    "ACT", "BANK", "HOME", "CYBER", "LAYER", "MEME", "THE", "AND",
    "FOR", "ARE", "NOT", "BUT", "CAN", "ONE", "ALL", "ANY", "NEW",
    "NOW", "LOW", "HIGH", "TOP", "USE", "GET", "GOT", "HAS", "HAD",
    "HIS", "HER", "OUR", "OUT", "YOU", "YOUR", "ITS", "IN", "ON",
    "OR", "AS", "AT", "BY", "TO", "OF", "IT", "IS", "BE", "WE",
    "HE", "SHE", "DO", "GO", "NO", "SO", "UP", "DOWN", "AR", "OP",
    "AI", "ME", "MY", "US", "IF", "THAN", "THEN", "THIS", "THAT",
    "THEIR", "THEM", "WITH", "FROM", "OVER", "UNDER", "MORE", "MOST",
    "JUST", "BACK", "NEXT", "LAST", "FIRST", "STILL", "EVEN", "ONLY",
    "MAY", "MUST", "WILL", "WOULD", "COULD", "SHOULD",
}


# =============================================================
# Utility functions
# =============================================================

def _clean_text(value: str) -> str:
    value = str(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _sentence_list(text: str) -> list[str]:
    text = _clean_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


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

    for article in articles:
        url = article.get("url")
        headline = _clean_text(article.get("headline", ""))
        
        if not url:
            continue

        if url in seen_urls:
            continue

        if not headline:
            continue

        detected_ticker = _detect_ticker(article, binance_tickers)
        is_fallback = False

        # Jodi ticker na paoa jay, tobe fallback (BTC, XAU, ARB) bosbe
        if not detected_ticker:
            ticker = random.choice(["BTC", "XAU", "ARB"])
            is_fallback = True
            print(f"[news] No ticker found, applied fallback: ${ticker}")
        else:
            ticker = detected_ticker.upper().strip()
            # Jodi regular ticker thake, tahole blocked_tickers check hobe
            if ticker in blocked_tickers:
                print(f"[news] SKIP — Ticker ${ticker} already posted today.")
                continue

        article["ticker"] = ticker
        
        # Image logic: 
        # - Jodi fallback hoy (mane news-e kono coin highlight chhilo na), tahole news-er original image thakbe.
        # - Jodi regular coin highlight thake, tahole oi coin-er official logo bosbe.
        if is_fallback:
            article["image_url"] = (
                article.get("image_url") 
                or article.get("urlToImage") 
                or article.get("image")
            )
        else:
            article["image_url"] = COIN_LOGOS.get(
                ticker, 
                article.get("image_url") or article.get("urlToImage") or article.get("image")
            )

        candidates.append(article)

    if not candidates:
        print("[news] No eligible crypto article found.")
        return None

    pool = candidates[:10]
    article = random.choice(pool)

    print(f"[news] Selected crypto article: ${article.get('ticker')} — {article.get('headline')}")
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

    headline = _clean_text(article.get("headline", ""))
    summary = _clean_text(article.get("summary", ""))

    headline_upper = headline.upper()
    summary_upper = summary.upper()
    full_text = f"{headline} {summary}"
    lower_text = full_text.lower()

    # 1. Explicit $TICKER in headline
    explicit_tickers = re.findall(r"\$([A-Z][A-Z0-9]{1,14})\b", headline_upper)
    for ticker in explicit_tickers:
        ticker = ticker.upper()
        if ticker in binance_tickers and ticker not in COMMON_WORD_TICKERS:
            return ticker

    # 2. Explicit $TICKER in summary
    explicit_summary_tickers = re.findall(r"\$([A-Z][A-Z0-9]{1,14})\b", summary_upper)
    for ticker in explicit_summary_tickers:
        ticker = ticker.upper()
        if ticker in binance_tickers and ticker not in COMMON_WORD_TICKERS:
            return ticker

    # 3. Full crypto asset names in HEADLINE
    for name in sorted(ASSET_NAME_MAP, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", headline_upper):
            ticker = ASSET_NAME_MAP[name]
            if ticker in binance_tickers and ticker not in COMMON_WORD_TICKERS:
                return ticker

    # 4. Full crypto asset names anywhere in summary/content
    for name in sorted(ASSET_NAME_MAP, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", lower_text, re.IGNORECASE):
            ticker = ASSET_NAME_MAP[name]
            if ticker in binance_tickers and ticker not in COMMON_WORD_TICKERS:
                return ticker

    return None


def _detect_asset_name(ticker: str) -> str | None:
    if not ticker:
        return None
    ticker = ticker.upper().strip()
    return KNOWN_ASSET_NAMES.get(ticker, ticker)


# =============================================================
# Python fallback post & generation
# =============================================================

def _python_fallback_post(article: dict, ticker: str) -> dict:
    ticker = ticker.upper().strip()
    asset_name = _detect_asset_name(ticker) or ticker
    headline = _clean_text(article.get("headline", ""))
    summary = _clean_text(article.get("summary", ""))

    title = f"{asset_name} (${ticker}): {headline}"
    if len(title) > 180:
        title = title[:177].rstrip() + "..."

    summary_sentences = _sentence_list(summary)
    paragraph_1 = headline if headline.endswith((".", "!", "?")) else headline + "."
    paragraph_2 = f"According to the report, {summary_sentences[0] if summary_sentences else 'developments continue.'}"
    paragraph_3 = f"The report keeps the focus on the specific development involving {asset_name} (${ticker})."

    body = "\n\n".join([paragraph_1, paragraph_2, paragraph_3])

    return {
        "title": title,
        "body": body,
        "url": article.get("url"),
        "ticker": ticker,
        "image_url": article.get("image_url"),
    }


def _validate_generated_post(post: dict, ticker: str) -> dict:
    ticker = ticker.upper().strip()
    title = str(post.get("title", "")).strip()
    body = str(post.get("body", "")).strip()

    if not title or not body:
        raise RuntimeError("AI returned an empty title or body.")

    expected_marker = f"(${ticker})"
    if expected_marker.upper() not in title.upper():
        raise RuntimeError(f"AI title does not contain verified ticker ${ticker}")

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


def generate_news_post(article: dict) -> dict:
    ticker = article.get("ticker")
    if not ticker:
        ticker = "BTC"

    ticker = ticker.upper().strip()
    asset_name = _detect_asset_name(ticker) or "Bitcoin"

    try:
        client = Groq(api_key=cfg.GROQ_API_KEY)
        user_prompt = f"""Article headline:\n\n{article.get('headline')}\n\nArticle summary:\n\n{article.get('summary')}\n\nVerified ticker: ${ticker}\n\nReturn JSON with title and body."""

        completion = client.chat.completions.create(
            model=cfg.GROQ_MODEL,
            temperature=0.6,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = completion.choices[0].message.content or ""
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        post = json.loads(cleaned)

        post = _validate_generated_post(post, ticker)
        post["url"] = article.get("url")
        post["ticker"] = ticker
        post["image_url"] = article.get("image_url")
        return post

    except Exception:
        return _python_fallback_post(article, ticker)


def format_news_post(post: dict) -> str:
    if not post:
        raise RuntimeError("Refusing to publish: empty post.")

    title = str(post.get("title", "")).strip()
    body = str(post.get("body", "")).strip()
    ticker = str(post.get("ticker", "BTC")).upper().strip()

    body = re.sub(
        rf"\n*\*\*\s*\${re.escape(ticker)}\s*\*\*\s*$",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()

    parts = [p for p in [title, body, f"**${ticker}**"] if p]
    text = "\n\n".join(parts).strip()

    if len(text) > cfg.CHAR_LIMIT:
        text = text[:cfg.CHAR_LIMIT].rstrip()

    return text
