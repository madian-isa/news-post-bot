# News Post Bot (Binance Square)

Posts short, strictly factual crypto news posts to Binance Square — never
trade calls, never invented numbers or tickers. Fully separate from any
trade-setup bot.

## Flow

1. **`news_fetch.py`** — pulls recent crypto news from Finnhub (free tier).
2. **`news_post_generator.py`** — picks one article not already covered,
   sends it to Groq, gets back a title/body/closing-line JSON. Only
   mentions a coin ticker if it's actually detected in the source article.
3. **`square_post.py`** — publishes the text post to Binance Square.
4. **`news_state.py`** — tracks which article URLs have been covered and
   how many posts have gone out today, in `news_bot_state.json`.
5. **`main.py`** — orchestrates one run: pick article → generate → post.

## Setup

```bash
pip install -r requirements.txt
```

Set these as **GitHub repo secrets** (Settings → Secrets and variables →
Actions → Secrets):
- `GROQ_API_KEY`
- `BINANCE_SQUARE_OPENAPI_KEY`
- `FINNHUB_API_KEY`

Set as a **repo variable** (same page, "Variables" tab):
- `DRY_RUN` = `true` (default — prints the post instead of publishing;
  switch to `false` once you're happy with the output)

## Scheduling

`.github/workflows/news-post-bot.yml` runs this every 3 hours. **GitHub's
own cron scheduler can be unreliable** (known platform issue) — for more
consistent timing, use an external service like
[cron-job.org](https://cron-job.org) to call:

```
POST https://api.github.com/repos/<you>/<this-repo>/actions/workflows/news-post-bot.yml/dispatches
Authorization: Bearer <a GitHub Personal Access Token with "workflow" scope>
Accept: application/vnd.github+json
Content-Type: application/json

{"ref":"main"}
```

## Local testing

```bash
DRY_RUN=true python -m src.main
```
