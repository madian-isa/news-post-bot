"""
news_post_generator.py

Short, factual crypto news posts (not trade calls). Style:

    🚨 2.4 MILLION ZEC JUST SPOKE — 99.9% BACKED 25-SECOND BLOCKS

    Zcash is back on the radar after nearly 2.4M ZEC participated in
    the latest NU7 governance vote...
    ...
    $ZEC is definitely one to keep on the radar as the upgrade develops.

Only ever writes about a REAL article pulled from Finnhub — never
invents a story, a number, or a coin ticker that isn't actually in the
source material.
"""

import re
import json
import random

from groq import Groq
from src import config as cfg
from src.news_fetch import fetch_crypto_news

SYSTEM_PROMPT = """You are a crypto news writer for Binance Square. You turn one real news
article into a short, punchy but strictly factual post.

Rules:
- Use ONLY the facts in the article given (headline + summary). Never invent numbers, quotes, or details not present in the source.
- "title" is a short, attention-grabbing all-caps hook, ideally built around a real number or stat from the article (like a vote count, a percentage, a dollar amount). Start it with one relevant emoji. If no real number is available, write a strong hook without inventing one.
- "body" is 3-5 short sentences/paragraphs in plain, natural language explaining what happened and why it matters. No hype, no "to the moon", no financial advice. Just clear, factual reporting.
- "closing" is ONE forward-looking sentence. If a specific coin ticker is clearly the subject (given below), end mentioning it naturally with a $ prefix (e.g. "$ZEC is one to watch as..."). If no specific coin is given, write a general closing line with no ticker.
- Never use hashtags. Minimal emoji — just the one in the title.
- Output ONLY valid JSON, no markdown fences, no preamble."""


def get_candidate_article(seen_urls: set) -> dict | None:
    """Returns one Finnhub article not already covered, or None if nothing
    new/substantial is available. Prefers articles with a real summary."""
    articles = fetch_crypto_news()
    candidates = [
        a for a in articles
        if a.get("url") and a["url"] not in seen_urls
        and a.get("headline") and len((a.get("summary") or "")) > 40
    ]
    if not candidates:
        return None
    pool = candidates[:10] or candidates
    return random.choice(pool)


def _detect_ticker(article: dict) -> str | None:
    """Finds a coin ticker actually mentioned in the article — never
    guesses one that isn't there."""
    haystack = f"{article.get('headline','')} {article.get('summary','')}".upper()
    for base in cfg.KNOWN_TICKERS:
        if re.search(rf"\b{re.escape(base)}\b", haystack):
            return base
    return None


def generate_news_post(article: dict) -> dict:
    client = Groq(api_key=cfg.GROQ_API_KEY)
    ticker = _detect_ticker(article)

    user_prompt = f"""Article headline: {article.get('headline')}
Article summary: {article.get('summary')}
Source: {article.get('source', 'unknown')}
Detected coin ticker (use this exact one if writing a closing line with a ticker; if this is empty, do NOT invent one): {ticker or ''}

Return JSON with exactly this shape:
{{
  "title": string,
  "body": string,
  "closing": string
}}"""

    completion = client.chat.completions.create(
        model=cfg.GROQ_MODEL,
        temperature=0.8,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = completion.choices[0].message.content or ""
    cleaned = raw.replace("```json", "").replace("```", "").strip()

    try:
        post = json.loads(cleaned)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Model did not return valid JSON: {raw}") from err

    post["url"] = article.get("url")
    post["ticker"] = ticker
    return post


def format_news_post(post: dict) -> str:
    lines = [post["title"].strip(), "", post["body"].strip()]
    closing = post.get("closing", "").strip()
    if closing:
        lines += ["", closing]

    text = "\n".join(lines).strip()
    if len(text) > cfg.CHAR_LIMIT:
        text = text[: cfg.CHAR_LIMIT].rstrip()
    return text
