"""
news_post_generator.py

Generates short, factual Binance Square news posts.

Format:

Coin Name ($TICKER): Attention-grabbing headline

Paragraph 1 explaining the news.

Paragraph 2 explaining the important development.

Paragraph 3 explaining why it matters.

**$TICKER**

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

Paragraph 1:
Explain exactly what happened using ONLY facts from the article.

Paragraph 2:
Explain the important development, product, partnership, regulatory action,
or other relevant detail using ONLY facts from the article.

Paragraph 3:
Explain why the development matters using careful factual language.
Do not make unsupported predictions.

Final line:
**$TICKER**

STRICT RULES:

- Use ONLY facts contained in the article headline and summary.
- Never invent numbers, dates, partnerships, valuations, quotes, or events.
- If a ticker is provided, use that exact ticker.
- Never invent a ticker.
- The title should start with the company, project, or coin name.
- If a ticker is available, the title MUST contain it in this format:
  Company Name ($TICKER):
- The final line MUST be **$TICKER** when a ticker is available.
- Do NOT create a separate risk section.
- Do NOT use bullet points.
- Do NOT use hashtags.
- Do NOT use emojis.
- Do NOT use trading instructions.
- Do NOT say buy, sell, long, short, target, guaranteed, moon, or similar hype.
- Do NOT give investment advice.
- Use professional but natural English.
- Avoid repetitive AI-style phrases.
- Keep the post concise, around 100-140 words when possible.
- Output ONLY valid JSON.
- Do NOT output Markdown fences.

Return exactly:

{
  "title": string,
  "body": string,
  "closing": string
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
    Detect a ticker explicitly mentioned in the article.

    Never invents a ticker.
    """

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

    # First look for explicit $TICKER mentions.
    explicit_tickers = re.findall(
        r"\$([A-Z][A-Z0-9]{1,9})\b",
        haystack,
    )

    if explicit_tickers:
        for ticker in explicit_tickers:
            if ticker in cfg.KNOWN_TICKERS:
                return ticker

    # Then check known tickers appearing as standalone words.
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
    Detect a company/project name from known mappings or headline.

    This does not invent names.
    """

    haystack = (
        f"{article.get('headline', '')} "
        f"{article.get('summary', '')}"
    ).upper()

    # Known company -> ticker mappings.
    company_map = {
        "COINBASE": "COIN",
    }

    if ticker:
        for company, mapped_ticker in company_map.items():
            if (
                mapped_ticker == ticker
                and company in haystack
            ):
                return company.title()

    headline = (
        article.get("headline") or ""
    ).strip()

    if headline:
        # If the headline explicitly contains the ticker,
        # use the first meaningful part before ":".
        if ticker and re.search(
            rf"\b{re.escape(ticker)}\b",
            headline.upper(),
        ):
            first_part = headline.split(":", 1)[0].strip()

            if first_part:
                first_part = re.sub(
                    rf"\s*\(?\$?{re.escape(ticker)}\)?\s*",
                    " ",
                    first_part,
                    flags=re.IGNORECASE,
                ).strip()

                if first_part:
                    return first_part

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

Detected company/project name:
{company_name or 'NONE'}

Create the Binance Square post using ONLY the information above.

If a ticker is detected:

Title format:
Company Name ($TICKER): Hook

The final line must be:
**$TICKER**

If no ticker is detected:

Do NOT invent a ticker.
Do NOT create a fake $TICKER.
Use the company/project name only.

Return JSON only:

{{
  "title": string,
  "body": string,
  "closing": string
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
    title = post.get("title", "").strip()
    body = post.get("body", "").strip()
    closing = post.get("closing", "").strip()

    parts = []

    if title:
        parts.append(title)

    if body:
        parts.append(body)

    if closing:
        parts.append(closing)

    text = "\n\n".join(parts).strip()

    if len(text) > cfg.CHAR_LIMIT:
        text = text[:cfg.CHAR_LIMIT].rstrip()

    return text
