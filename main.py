"""
main.py

Single-run mode:
Each invocation attempts to publish ONE real crypto-news post.

Rules:
- Only valid crypto-asset articles are accepted.
- Same article URL cannot be posted twice.
- Same crypto ticker can be posted only ONCE per Bangladesh day.
- Daily post limit is enforced.
"""

import traceback

import config as cfg

from news_post_generator import (
    get_candidate_article,
    generate_news_post,
    format_news_post,
    _detect_ticker,
)

from square_post import post_text

from news_state import (
    load_state,
    save_state,
    can_post_more_today,
    ticker_posted_today,
    record_post,
)


def run_once():
    state = load_state()

    # ---------------------------------------------------------
    # 1. Check daily maximum post limit
    # ---------------------------------------------------------

    if not can_post_more_today(state):
        print(
            f"[news] daily cap reached "
            f"({cfg.NEWS_MAX_POSTS_PER_DAY}) — skipping this run."
        )
        return

    # ---------------------------------------------------------
    # 2. Find a new crypto article
    # ---------------------------------------------------------

    article = get_candidate_article(
        set(state.get("seen_urls", []))
    )

    if not article:
        print(
            "[news] no new valid crypto article found "
            "this run — skipping."
        )
        return

    # ---------------------------------------------------------
    # 3. Detect crypto ticker
    # ---------------------------------------------------------

    ticker = _detect_ticker(article)

    # HARD STOP:
    # Never publish an article without a real crypto ticker.
    if not ticker:
        print(
            "[news] article rejected — "
            "no valid crypto ticker detected."
        )
        return

    ticker = ticker.upper()

    print(
        f"[news] detected crypto asset: ${ticker}"
    )

    # ---------------------------------------------------------
    # 4. Same coin cannot be posted twice today
    # ---------------------------------------------------------

    if ticker_posted_today(state, ticker):
        print(
            f"[news] ${ticker} already posted today — skipping."
        )
        return

    # ---------------------------------------------------------
    # 5. Generate Binance Square post
    # ---------------------------------------------------------

    try:
        post = generate_news_post(article)

        # Make sure generated post still belongs to
        # the same verified ticker.
        if post.get("ticker") != ticker:
            print(
                f"[news] ticker mismatch — "
                f"expected ${ticker}, "
                f"got ${post.get('ticker')}"
            )
            return

        text = format_news_post(post)

        # -----------------------------------------------------
        # 6. Dry-run mode
        # -----------------------------------------------------

        if cfg.DRY_RUN:
            print("\n[DRY RUN] would post:")
            print("-" * 60)
            print(text)
            print("-" * 60)
            print(
                f"[DRY RUN] crypto: ${ticker}"
            )
            print(
                f"[DRY RUN] source: {article.get('url')}"
            )
            print(
                "[DRY RUN] nothing posted to Binance Square.\n"
            )
            return

        # -----------------------------------------------------
        # 7. Publish to Binance Square
        # -----------------------------------------------------

        result = post_text(text)

        print(
            f"[news] published -> "
            f"{result.get('link')} "
            f"(crypto: ${ticker}) "
            f"(source: {article.get('url')})"
        )

        # -----------------------------------------------------
        # 8. Save successful post
        # -----------------------------------------------------

        state = record_post(
            state,
            article["url"],
            ticker,
        )

        save_state(state)

        print(
            f"[news] saved: ${ticker} "
            f"cannot be posted again today."
        )

    except Exception as err:
        print(f"[news] failed: {err}")
        traceback.print_exc()


if __name__ == "__main__":
    run_once()
