"""
config.py

All settings read from environment variables only.
Never hard-code API keys here.

Set secrets in:
GitHub repo
→ Settings
→ Secrets and variables
→ Actions
"""

import os


# ---------------------------------------------------------
# API KEYS
# ---------------------------------------------------------

BINANCE_SQUARE_OPENAPI_KEY = os.environ.get(
    "BINANCE_SQUARE_OPENAPI_KEY",
    "",
)

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    "",
)

GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

FINNHUB_API_KEY = os.environ.get(
    "FINNHUB_API_KEY",
    "",
)

# CoinMarketCap — secondary news source
CMC_API_KEY = os.environ.get(
    "CMC_API_KEY",
    "",
)


# ---------------------------------------------------------
# POST SETTINGS
# ---------------------------------------------------------

CHAR_LIMIT = 2000


# ---------------------------------------------------------
# NEWS STATE
# ---------------------------------------------------------

# How many recent article URLs to remember,
# so the same story isn't posted twice.

NEWS_STATE_FILE = os.environ.get(
    "NEWS_BOT_STATE_FILE",
    "news_bot_state.json",
)

NEWS_MAX_POSTS_PER_DAY = int(
    os.environ.get(
        "NEWS_MAX_POSTS_PER_DAY",
        "8",
    )
)

NEWS_SEEN_HISTORY_SIZE = int(
    os.environ.get(
        "NEWS_SEEN_HISTORY_SIZE",
        "100",
    )
)


# ---------------------------------------------------------
# DRY RUN
# ---------------------------------------------------------

# When true, nothing is posted to Binance Square.
#
# GitHub Actions currently sets:
# DRY_RUN=false
#
# Therefore the bot is LIVE.

DRY_RUN = (
    os.environ.get(
        "DRY_RUN",
        "true",
    ).lower()
    not in (
        "false",
        "0",
        "no",
    )
)


# ---------------------------------------------------------
# KNOWN TICKERS
# ---------------------------------------------------------

# Used only to detect a real coin ticker mentioned
# in an article.

KNOWN_TICKERS = {
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "TRX", "TON", "LINK",
    "AVAX", "DOT", "LTC", "BCH", "ATOM", "XLM", "ETC", "NEAR", "FIL", "EOS",
    "ALGO", "EGLD", "THETA", "XTZ", "KAVA", "VET", "ICP", "HBAR", "RUNE",
    "IOTA", "NEO", "WAVES", "DASH", "ZEC", "QTUM", "ONT", "ZRX", "BAT",
    "OMG", "KSM", "RVN", "HOT", "IOST", "ZIL", "ONE", "AAVE", "UNI", "MKR",
    "LDO", "SNX", "CRV", "COMP", "SUSHI", "YFI", "DYDX", "GMX", "PENDLE",
    "WOO", "APT", "ARB", "OP", "SUI", "INJ", "STX", "IMX", "MANTA", "STRK",
    "SEI", "TIA", "AR", "KAS", "ROSE", "CFX", "CELO", "FLOW", "SAND",
    "MANA", "GALA", "AXS", "ENJ", "CHZ", "APE", "GMT", "MAGIC", "PEOPLE",
    "FET", "AGIX", "OCEAN", "RNDR", "GRT", "ARKM", "WLD", "PEPE", "WIF",
    "BONK", "FLOKI", "SHIB", "ORDI", "JUP", "NOT", "BAND", "SKL", "ANKR",
    "CTSI", "MASK", "BLUR", "LPT", "HIGH", "PYTH", "JTO", "TAO", "ENA",
    "ONDO",
}
