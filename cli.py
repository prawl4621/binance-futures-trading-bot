"""
cli.py — Command-line interface for the trading bot.

All user-facing text, argument parsing, and pretty-printing live here.
The CLI layer never imports requests or touches the API directly.
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from typing import Optional

from client import BinanceAPIError, BinanceFuturesClient, BinanceNetworkError
from config import VALID_ORDER_TYPES, VALID_SIDES, VALID_SYMBOLS, load_config
from logger import get_logger
from models import OrderRequest

log = get_logger("cli")

# ── ANSI helpers ──────────────────────────────────────────────────────────────

def _green(s: str) -> str: return f"\033[32m{s}\033[0m"
def _red(s: str)   -> str: return f"\033[31m{s}\033[0m"
def _bold(s: str)  -> str: return f"\033[1m{s}\033[0m"
def _cyan(s: str)  -> str: return f"\033[36m{s}\033[0m"


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=_bold("Binance Futures Testnet — Order Placement CLI"),
        epilog=textwrap.dedent(
            """
            Examples:
              Market BUY 0.01 BTC:
                python main.py --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

              Limit SELL 0.005 ETH at 3000 USDT:
                python main.py --symbol ETHUSDT --side SELL --type LIMIT --qty 0.005 --price 3000

              Limit BUY 0.1 SOL at 150 USDT:
                python main.py --symbol SOLUSDT --side BUY --type LIMIT --qty 0.1 --price 150

            Environment Variables:
              BINANCE_TESTNET_API_KEY     Your Binance Futures Testnet API key
              BINANCE_TESTNET_API_SECRET  Your Binance Futures Testnet API secret

            Supported symbols: """ + ", ".join(sorted(VALID_SYMBOLS))
        ),
    )

    parser.add_argument(
        "--symbol", "-s",
        required=True,
        metavar="SYMBOL",
        help=f"Trading pair (e.g. BTCUSDT). Supported: {', '.join(sorted(VALID_SYMBOLS))}",
    )
    parser.add_argument(
        "--side",
        required=True,
        choices=list(VALID_SIDES),
        metavar="SIDE",
        help="Order side: BUY or SELL",
    )
    parser.add_argument(
        "--type", "-t",
        dest="order_type",
        required=True,
        choices=list(VALID_ORDER_TYPES),
        metavar="TYPE",
        help="Order type: MARKET or LIMIT",
    )
    parser.add_argument(
        "--qty", "-q",
        dest="quantity",
        required=True,
        metavar="QTY",
        help="Order quantity (e.g. 0.01 for 0.01 BTC)",
    )
    parser.add_argument(
        "--price", "-p",
        default=None,
        metavar="PRICE",
        help="Limit price in USDT — required for LIMIT orders, forbidden for MARKET",
    )
    parser.add_argument(
        "--no-ping",
        action="store_true",
        default=False,
        help="Skip connectivity ping before placing the order",
    )
    return parser


# ── Display helpers ───────────────────────────────────────────────────────────

def print_request_summary(order: OrderRequest) -> None:
    print()
    print(_bold(_cyan("═══ Order Request Summary ══════════════════════════════")))
    print(f"  Symbol     : {_bold(order.symbol)}")
    print(f"  Side       : {_bold(order.side)}")
    print(f"  Type       : {order.order_type}")
    print(f"  Quantity   : {order.quantity}")
    if order.price:
        print(f"  Price      : {order.price} USDT")
    else:
        print(f"  Price      : (market — best available)")
    print(_cyan("═════════════════════════════════════════════════════════"))
    print()


def print_success(response_display: str) -> None:
    print()
    print(response_display)
    print()
    print(_green("✓  Order placed successfully!"))
    print()


def print_failure(reason: str) -> None:
    print()
    print(_red(f"✗  Order FAILED: {reason}"))
    print()


# ── Main entry point ──────────────────────────────────────────────────────────

def run(argv: Optional[list[str]] = None) -> int:
    """
    Parse arguments, validate, place order, print result.
    Returns 0 on success, 1 on failure (so main.py can sys.exit() cleanly).
    """
    parser = build_parser()
    args   = parser.parse_args(argv)

    log.debug(
        "CLI args received: symbol=%s side=%s type=%s qty=%s price=%s",
        args.symbol, args.side, args.order_type, args.quantity, args.price,
    )

    # ── Step 1 — Validate & build order request ───────────────────────────────
    try:
        order = OrderRequest.from_raw(
            symbol     = args.symbol,
            side       = args.side,
            order_type = args.order_type,
            quantity   = args.quantity,
            price      = args.price,
        )
    except ValueError as exc:
        log.error("Input validation failed: %s", exc)
        print(_red(f"\n✗  Invalid input: {exc}\n"))
        return 1

    print_request_summary(order)

    # ── Step 2 — Load credentials & build client ──────────────────────────────
    try:
        config = load_config()
    except RuntimeError as exc:
        log.error("Configuration error: %s", exc)
        print(_red(f"\n✗  Configuration error:\n{exc}\n"))
        return 1

    client = BinanceFuturesClient(config)

    # ── Step 3 — Optional connectivity ping ───────────────────────────────────
    if not args.no_ping:
        print(_cyan("  Checking connectivity to testnet..."))
        if not client.ping():
            print_failure(
                "Could not reach the Binance Futures Testnet. "
                "Check your internet connection or pass --no-ping to skip."
            )
            return 1
        print(_green("  Testnet reachable ✓"))
        print()

    # ── Step 4 — Place the order ──────────────────────────────────────────────
    try:
        response = client.place_order(order)
        print_success(response.display())
        return 0

    except BinanceAPIError as exc:
        log.error("API error placing order: %s", exc)
        error_hints = {
            -1102: "Mandatory parameter missing — check symbol/qty/price.",
            -1111: "Quantity precision too high — use fewer decimal places.",
            -1121: "Invalid symbol — check the --symbol argument.",
            -2010: "Order would immediately trigger or insufficient margin.",
            -4003: "Quantity below minimum — try a larger amount.",
        }
        hint = error_hints.get(exc.code, "")
        msg  = f"{exc}"
        if hint:
            msg += f"\n  Hint: {hint}"
        print_failure(msg)
        return 1

    except BinanceNetworkError as exc:
        log.error("Network error placing order: %s", exc)
        print_failure(f"Network error — {exc}")
        return 1

    except KeyboardInterrupt:
        print(_red("\n  Interrupted by user."))
        return 1

    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        print_failure(f"Unexpected error: {exc}")
        return 1
