"""
main.py

Single-run mode.

Each invocation attempts to publish ONE real crypto-news post.

Rules:
- Only Binance-verified crypto assets are allowed.
- Same article URL cannot be posted twice.
- Same crypto ticker can only be posted ONCE per Bangladesh day.
- If one coin is blocked, another eligible coin is searched.
- Daily post limit is enforced.
"""

import traceback

import config as cfg

from news_post_generator import (
    get_candidate_article,
    generate_news_post,
    format_news_post,
)

from square_post import post_text

from news_state import (
    load_state,
    save_state,
    can_post_more_today,
    record_post,
)


def run_once():
    # ---------------------------------------------------------
    # 1. Load state
    # ---------------------------------------------------------

    state = load_state()

    # ---------------------------------------------------------
    # 2. Daily maximum
    # ---------------------------------------------------------

    if not can_post_more_today(state):

        print(
            f"[news] daily cap reached "
            f"({cfg.NEWS_MAX_POSTS_PER_DAY}) "
            f"— skipping this run."
        )

        return

    # ---------------------------------------------------------
    # 3. Get today's blocked crypto tickers
    # ---------------------------------------------------------

    blocked_tickers = {
        str(t).upper()
        for t in state.get(
            "posted_tickers",
            [],
        )
    }

    print(
        f"[news] today's blocked tickers: "
        f"{sorted(blocked_tickers)}"
    )

    # ---------------------------------------------------------
    # 4. Find eligible article
    #
    # IMPORTANT:
    # get_candidate_article() itself skips:
    #
    # - old article URLs
    # - non-crypto articles
    # - non-Binance-listed assets
    # - today's already-posted crypto
    #
    # Therefore if BTC is blocked, it keeps looking for
    # another eligible coin instead of stopping the run.
    # ---------------------------------------------------------

    article = get_candidate_article(
        set(
            state.get(
                "seen_urls",
                [],
            )
        ),
        blocked_tickers,
    )

    if not article:

        print(
            "[news] no eligible crypto article found "
            "this run — nothing to publish."
        )

        return

    # ---------------------------------------------------------
    # 5. Get verified ticker
    # ---------------------------------------------------------

    ticker = article.get("ticker")

    if not ticker:

        print(
            "[news] selected article has no verified ticker "
            "— refusing to publish."
        )

        return

    ticker = str(
        ticker
    ).upper()

    print(
        f"[news] preparing post for ${ticker}"
    )

    # ---------------------------------------------------------
    # 6. Generate + publish
    # ---------------------------------------------------------

    try:

        # Generate AI post
        post = generate_news_post(
            article
        )

        # Verify returned ticker
        generated_ticker = str(
            post.get("ticker", "")
        ).upper()

        if generated_ticker != ticker:

            raise RuntimeError(
                f"Ticker mismatch: "
                f"expected ${ticker}, "
                f"got ${generated_ticker}"
            )

        # Format final Binance Square post
        text = format_news_post(
            post
        )

        # -----------------------------------------------------
        # 7. DRY RUN
        # -----------------------------------------------------

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
                "[DRY RUN] nothing posted "
                "to Binance Square.\n"
            )

            return

        # -----------------------------------------------------
        # 8. Publish
        # -----------------------------------------------------

        result = post_text(
            text
        )

        print(
            f"[news] published -> "
            f"{result.get('link')} "
            f"(crypto: ${ticker})"
        )

        print(
            f"[news] source: "
            f"{article.get('url')}"
        )

        # -----------------------------------------------------
        # 9. Save state
        #
        # Only after successful publication.
        # -----------------------------------------------------

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
            f"${ticker} is blocked "
            f"for the rest of today."
        )

    except Exception as err:

        print(
            f"[news] failed: {err}"
        )

        traceback.print_exc()


if __name__ == "__main__":
    run_once()
