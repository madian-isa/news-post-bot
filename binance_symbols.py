"""
binance_symbols.py

Loads the current Binance Spot crypto symbols.

Purpose:
- Avoid maintaining a fixed list of 100+ crypto tickers manually.
- Validate whether a detected ticker is currently listed on Binance Spot.
- Cache the result during the current bot run.
"""

import time
import requests


BINANCE_EXCHANGE_INFO_URL = (
    "https://data-api.binance.vision/api/v3/exchangeInfo"
)

_CACHE_TTL_SECONDS = 60 * 60

_cache = {
    "fetched_at": 0,
    "tickers": set(),
}


def get_binance_crypto_tickers() -> set[str]:
    """
    Return currently tradable Binance Spot base-asset tickers.

    Example:
        BTC
        ETH
        SOL
        ZEC
        NEWT

    Only symbols with:
    - status == TRADING
    - quote assets commonly used for crypto markets
    are included.
    """

    now = time.time()

    # ---------------------------------------------------------
    # Use cache if still fresh
    # ---------------------------------------------------------

    if (
        _cache["tickers"]
        and now - _cache["fetched_at"] < _CACHE_TTL_SECONDS
    ):
        return _cache["tickers"]

    try:
        response = requests.get(
            BINANCE_EXCHANGE_INFO_URL,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

    except requests.RequestException as err:
        print(
            f"[binance_symbols] failed to fetch exchange info: {err}"
        )

        # If we already have an older cache, keep using it.
        if _cache["tickers"]:
            return _cache["tickers"]

        return set()

    except ValueError as err:
        print(
            f"[binance_symbols] invalid JSON response: {err}"
        )

        if _cache["tickers"]:
            return _cache["tickers"]

        return set()

    symbols = data.get("symbols", [])

    tickers = set()

    # ---------------------------------------------------------
    # Crypto quote assets
    # ---------------------------------------------------------

    crypto_quotes = {
        "USDT",
        "USDC",
        "FDUSD",
        "BTC",
        "ETH",
        "BNB",
        "TRY",
        "BRL",
        "EUR",
        "GBP",
        "AUD",
        "DAI",
        "TUSD",
    }

    # ---------------------------------------------------------
    # Extract base assets
    # ---------------------------------------------------------

    for symbol in symbols:

        if not isinstance(symbol, dict):
            continue

        if symbol.get("status") != "TRADING":
            continue

        base_asset = str(
            symbol.get("baseAsset", "")
        ).upper()

        quote_asset = str(
            symbol.get("quoteAsset", "")
        ).upper()

        if not base_asset:
            continue

        if quote_asset not in crypto_quotes:
            continue

        tickers.add(base_asset)

    # ---------------------------------------------------------
    # Safety
    # ---------------------------------------------------------

    if not tickers:
        print(
            "[binance_symbols] no Binance crypto symbols found."
        )

        if _cache["tickers"]:
            return _cache["tickers"]

        return set()

    _cache["fetched_at"] = now
    _cache["tickers"] = tickers

    print(
        f"[binance_symbols] loaded "
        f"{len(tickers)} Binance crypto assets."
    )

    return tickers


def is_binance_crypto_ticker(ticker: str) -> bool:
    """
    Check whether a ticker is currently a Binance Spot crypto asset.
    """

    if not ticker:
        return False

    ticker = ticker.upper().strip()

    tickers = get_binance_crypto_tickers()

    return ticker in tickers
