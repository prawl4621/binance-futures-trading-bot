"""
config.py — Centralised configuration for the Binance Futures Testnet bot.
All environment variables are read here; nowhere else calls os.environ.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


TESTNET_BASE_URL = "https://testnet.binancefuture.com"

VALID_SYMBOLS = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT",
}
VALID_SIDES      = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT"}

LOG_FILE    = "trading_bot.log"
LOG_LEVEL   = os.getenv("LOG_LEVEL", "DEBUG")
RECV_WINDOW = 5_000          # ms


@dataclass(frozen=True)
class BotConfig:
    api_key:    str
    api_secret: str
    base_url:   str = TESTNET_BASE_URL
    recv_window: int = RECV_WINDOW

    # Extra safety: never let real-money URLs slip in.
    def __post_init__(self) -> None:
        if "testnet" not in self.base_url.lower():
            raise ValueError(
                f"Refusing to run against non-testnet URL: {self.base_url}"
            )


def load_config() -> BotConfig:
    """
    Load API credentials from environment variables.
    Raises RuntimeError with a clear message when either key is missing.
    """
    api_key    = os.getenv("BINANCE_TESTNET_API_KEY",    "").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET", "").strip()

    missing: list[str] = []
    if not api_key:
        missing.append("BINANCE_TESTNET_API_KEY")
    if not api_secret:
        missing.append("BINANCE_TESTNET_API_SECRET")

    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + "\n\nExport them before running:\n"
            + "\n".join(f"  export {v}=<your_value>" for v in missing)
        )

    return BotConfig(api_key=api_key, api_secret=api_secret)
