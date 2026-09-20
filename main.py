"""
main.py

Single-run mode.

Each invocation attempts to publish ONE crypto-news post.

Rules:
- Only Binance-listed crypto assets are allowed.
- Same article URL cannot be posted twice.
- Same crypto ticker CAN be posted multiple times in the same
  Bangladesh day, as long as the article URL is different.
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
    # 3. Find eligible article
    #
    # IMPORTANT:
    # We do NOT block tickers based on today's previous posts.
    #
    # Same ticker + different article = allowed.
    # Same article URL = blocked by seen_urls.
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
    # 4. Find eligible article
    # =========================================================

    article = get_candidate_article(
        seen_urls,
    )

    if not article:

        print(
            "[news] no eligible crypto article "
            "found this run."
        )

        return

    # =========================================================
    # 5. Verified ticker
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
    ).upper()

    print(
        f"[news] preparing post for ${ticker}"
    )

    image_paths = []

    try:

        # =====================================================
        # 6. Generate post text
        # =====================================================

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

        print(
            f"[news] generated post length: "
            f"{len(text)} chars"
        )

        # =====================================================
        # 7. Prepare ONLY crypto logo
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
        # 8. DRY RUN
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
        # 9. Publish
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
        # 10. Publication result
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
        # 11. Save state ONLY after publication
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
            f"${ticker} published."
        )

    except Exception as err:

        print(
            f"[news] failed: {err}"
        )

        traceback.print_exc()

    finally:

        # =====================================================
        # 12. Cleanup images
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
