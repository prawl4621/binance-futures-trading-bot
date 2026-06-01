"""
main.py — Entry point for the Binance Futures Testnet trading bot.

Usage:
  python main.py --help
  python main.py --symbol BTCUSDT --side BUY  --type MARKET --qty 0.01
  python main.py --symbol ETHUSDT --side SELL --type LIMIT  --qty 0.005 --price 3000
"""
from __future__ import annotations

import sys

from cli import run
from logger import get_logger

log = get_logger("main")


def main() -> None:
    log.debug("Trading bot starting (args=%s)", sys.argv[1:])
    exit_code = run()
    log.debug("Trading bot exiting (code=%d)", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
