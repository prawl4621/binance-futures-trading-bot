# Binance Futures Testnet — Trading Bot

A clean, production-structured Python CLI application for placing Market and Limit orders on the **Binance USDT-M Futures Testnet**.

---

## Features

| Feature | Detail |
|---|---|
| Order types | `MARKET` and `LIMIT` |
| Order sides | `BUY` and `SELL` |
| Input validation | Symbols, sides, types, numeric quantity/price, price rules per type |
| Structured logging | Coloured console (INFO+) + rotating file (DEBUG+) → `trading_bot.log` |
| Error handling | Invalid CLI input · Binance API errors · Network/timeout failures |
| Retry logic | Automatic 3-attempt retry on 5xx / connection errors |
| Safety guard | Refuses to run against non-testnet URLs |
| No heavy deps | Only `requests` + stdlib — no pandas, numpy, or broker SDKs |

---

## Project Structure

```
trading_bot/
├── main.py          # Entry point — wires up the CLI
├── cli.py           # Argument parsing, display, error surfacing
├── client.py        # Binance REST client (signing, HTTP, response parsing)
├── models.py        # Validated OrderRequest + OrderResponse dataclasses
├── config.py        # Configuration, environment loading, constants
├── logger.py        # Shared logging setup (console + rotating file)
├── requirements.txt
└── README.md
```

**Dependency flow (one direction only):**
```
main → cli → client → models, config, logger
                       ↑
                  config, logger
```

---

## Setup

### 1. Get Testnet Credentials

1. Visit [testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account
3. Navigate to **API Management** → generate a key pair
4. Save the **API Key** and **Secret Key**

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Export Credentials

```bash
export BINANCE_TESTNET_API_KEY="your_api_key_here"
export BINANCE_TESTNET_API_SECRET="your_api_secret_here"
```

Or use a `.env` file and `source` it:
```bash
# .env
export BINANCE_TESTNET_API_KEY=abc123
export BINANCE_TESTNET_API_SECRET=xyz789
```
```bash
source .env
```

---

## Usage

```
python main.py --symbol SYMBOL --side BUY|SELL --type MARKET|LIMIT --qty QTY [--price PRICE]
```

### Options

| Flag | Short | Required | Description |
|---|---|---|---|
| `--symbol` | `-s` | ✅ | Trading pair (e.g. `BTCUSDT`) |
| `--side` | | ✅ | `BUY` or `SELL` |
| `--type` | `-t` | ✅ | `MARKET` or `LIMIT` |
| `--qty` | `-q` | ✅ | Order quantity (e.g. `0.01`) |
| `--price` | `-p` | LIMIT only | Limit price in USDT |
| `--no-ping` | | ❌ | Skip connectivity check |

### Examples

```bash
# Market BUY 0.01 BTC
python main.py --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

# Limit SELL 0.005 ETH at 3000 USDT
python main.py --symbol ETHUSDT --side SELL --type LIMIT --qty 0.005 --price 3000

# Market SELL 0.1 SOL
python main.py -s SOLUSDT --side SELL -t MARKET -q 0.1

# Limit BUY 10 DOGE at 0.15 USDT
python main.py --symbol DOGEUSDT --side BUY --type LIMIT --qty 10 --price 0.15
```

---

## Sample Output

```
  Checking connectivity to testnet...
  Testnet reachable ✓

═══ Order Request Summary ══════════════════════════════
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.01
  Price      : (market — best available)
═════════════════════════════════════════════════════════

┌─── Order Response ─────────────────────────────────┐
│  Order ID      : 3423650056
│  Client OID    : web_abc123def456
│  Symbol        : BTCUSDT
│  Side          : BUY
│  Type          : MARKET
│  Status        : FILLED
│  Orig Qty      : 0.01
│  Executed Qty  : 0.01
│  Avg Price     : 68452.30000
│  Time-In-Force : GTC
└────────────────────────────────────────────────────┘

✓  Order placed successfully!
```

---

## Logging

All activity is written to `trading_bot.log` (rotates at 5 MB, keeps 3 backups):

```
2024-01-15 14:32:01 | INFO     | trading_bot.cli    | Placing order: BUY 0.01 BTCUSDT [MARKET] (market price)
2024-01-15 14:32:01 | DEBUG    | trading_bot.client | POST https://testnet.binancefuture.com/fapi/v1/order params={...}
2024-01-15 14:32:01 | DEBUG    | trading_bot.client | HTTP POST ... → 200 (243 ms)
2024-01-15 14:32:01 | INFO     | trading_bot.client | Order placed — id=3423650056 status=FILLED executedQty=0.01
```

---

## Supported Symbols

`ADAUSDT` · `AVAXUSDT` · `BNBUSDT` · `BTCUSDT` · `DOGEUSDT` · `ETHUSDT` · `LINKUSDT` · `LTCUSDT` · `SOLUSDT` · `XRPUSDT`

---

## Error Handling

| Error type | Example | Behaviour |
|---|---|---|
| Missing env var | No API key set | Clear message with export instructions |
| Invalid symbol | `--symbol FAKEUSDT` | Rejected before any API call |
| Price on MARKET | `--type MARKET --price 100` | Rejected with explanation |
| Missing price on LIMIT | `--type LIMIT` (no `--price`) | Rejected with explanation |
| API error | Insufficient margin | Binance error code + hint |
| Network timeout | No internet | Retries 3× then clean failure message |
| Non-testnet URL | `BotConfig` guard | Raises `ValueError` at startup |

---

## Design Notes

- **Decimal arithmetic** — all quantities and prices use `decimal.Decimal` to avoid float precision issues when constructing API params.
- **Immutable models** — `OrderRequest` and `OrderResponse` are frozen dataclasses; mutation after construction is impossible.
- **Single responsibility** — the CLI layer never touches `requests`; the client layer never touches `argparse`.
- **No global state** — `BinanceFuturesClient` is instantiated per-run; the session is encapsulated inside it.
