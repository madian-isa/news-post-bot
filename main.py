"""
main.py

Single-run mode.

Each invocation attempts to publish ONE crypto-news post.

Rules:
- Only Binance-listed crypto assets are allowed.
- Same article URL cannot be posted twice.
- Same crypto ticker can only be posted once per Bangladesh day.
- Maximum daily posts are controlled by config.
- Uses up to 2 images:
    1. original news image
    2. crypto logo
- If images are unavailable, the bot falls back to text-only.
- If image upload fails, the bot automatically falls back to text-only.
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

    # ---------------------------------------------------------
    # 1. Load state
    # ---------------------------------------------------------

    state = load_state()

    # ---------------------------------------------------------
    # 2. Daily cap
    # ---------------------------------------------------------

    if not can_post_more_today(state):

        print(
            f"[news] daily cap reached "
            f"({cfg.NEWS_MAX_POSTS_PER_DAY}) "
            "— skipping this run."
        )

        return

    # ---------------------------------------------------------
    # 3. Today's blocked tickers
    # ---------------------------------------------------------

    blocked_tickers = {
        str(t).upper()
        for t in state.get(
            "posted_tickers",
            [],
        )
    }

    print(
        "[news] today's blocked tickers: "
        f"{sorted(blocked_tickers)}"
    )

    # ---------------------------------------------------------
    # 4. Find eligible article
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
            "[news] no eligible crypto article "
            "found this run."
        )

        return

    # ---------------------------------------------------------
    # 5. Verified ticker
    # ---------------------------------------------------------

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
    ).upper()

    print(
        f"[news] preparing post for ${ticker}"
    )

    image_paths = []

    try:

        # -----------------------------------------------------
        # 6. Generate post text
        # -----------------------------------------------------

        post = generate_news_post(
            article
        )

        generated_ticker = str(
            post.get(
                "ticker",
                "",
            )
        ).upper()

        if generated_ticker != ticker:

            raise RuntimeError(
                f"Ticker mismatch: "
                f"expected ${ticker}, "
                f"got ${generated_ticker}"
            )

        text = format_news_post(
            post
        )

        # -----------------------------------------------------
        # 7. Prepare images
        # -----------------------------------------------------

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
                "[news] continuing with text-only post."
            )

            image_paths = []

        print(
            f"[news] images ready: "
            f"{len(image_paths)}"
        )

        # -----------------------------------------------------
        # 8. DRY RUN
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

        # -----------------------------------------------------
        # 9. Publish
        # -----------------------------------------------------

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

                # -------------------------------------------------
                # IMPORTANT:
                # Binance image upload can fail with errors such as
                # "Can't get presigned url".
                #
                # Do NOT lose the whole news post.
                # Automatically retry as text-only.
                # -------------------------------------------------

                print(
                    "[news] image post failed: "
                    f"{image_post_error}"
                )

                print(
                    "[news] falling back to text-only post..."
                )

                result = post_text(
                    text
                )

                print(
                    "[news] text-only fallback succeeded."
                )

        else:

            print(
                "[news] no images available — "
                "publishing text-only."
            )

            result = post_text(
                text
            )

        # -----------------------------------------------------
        # 10. Publication result
        # -----------------------------------------------------

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
        # 11. Save state ONLY after successful publication
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
            f"${ticker} blocked for today."
        )

    except Exception as err:

        print(
            f"[news] failed: {err}"
        )

        traceback.print_exc()

    finally:

        # -----------------------------------------------------
        # 12. Cleanup downloaded images
        # -----------------------------------------------------

        cleanup_images(
            image_paths
        )


if __name__ == "__main__":
    run_once()
