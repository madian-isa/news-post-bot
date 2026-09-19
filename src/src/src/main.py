"""
main.py

Single-run mode: each invocation posts ONE real-news-based post, then
exits. A scheduler (GitHub Actions cron, or an external service like
cron-job.org since GitHub's own schedule trigger can be unreliable)
re-runs this periodically.
"""

import traceback

from src import config as cfg
from src.news_post_generator import get_candidate_article, generate_news_post, format_news_post
from src.square_post import post_text
from src.news_state import load_state, save_state, can_post_more_today, record_post


def run_once():
    state = load_state()

    if not can_post_more_today(state):
        print(f"[news] daily cap reached ({cfg.NEWS_MAX_POSTS_PER_DAY}) — skipping this run.")
        return

    article = get_candidate_article(set(state.get("seen_urls", [])))
    if not article:
        print("[news] no new substantial article found this run — skipping.")
        return

    try:
        post = generate_news_post(article)
        text = format_news_post(post)

        if cfg.DRY_RUN:
            print("\n[DRY RUN] would post:")
            print("-" * 40)
            print(text)
            print("-" * 40)
            print(f"[DRY RUN] source: {article.get('url')}")
            print("[DRY RUN] nothing posted to Binance Square.\n")
            return

        result = post_text(text)
        print(f"[news] published -> {result.get('link')} (source: {article.get('url')})")

        state = record_post(state, article["url"])
        save_state(state)

    except Exception as err:
        print(f"[news] failed: {err}")
        traceback.print_exc()


if __name__ == "__main__":
    run_once()
