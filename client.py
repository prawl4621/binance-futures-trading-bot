"""
client.py — Low-level Binance Futures Testnet REST client.

Responsibilities:
  * HMAC-SHA256 request signing
  * Timestamping every signed request
  * Sending HTTP requests with timeout + retry on transient errors
  * Logging full request/response detail to the log file
  * Mapping HTTP / Binance error codes → descriptive Python exceptions

No CLI logic lives here.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import BotConfig
from logger import get_logger
from models import OrderRequest, OrderResponse

log = get_logger("client")

# ── Custom exceptions ──────────────────────────────────────────────────────────

class BinanceAPIError(Exception):
    """Raised when Binance returns a well-formed error payload."""
    def __init__(self, code: int, msg: str) -> None:
        self.code = code
        self.msg  = msg
        super().__init__(f"Binance API Error [{code}]: {msg}")


class BinanceNetworkError(Exception):
    """Raised on connection failures, timeouts, or unexpected HTTP status."""


# ── Client ────────────────────────────────────────────────────────────────────

class BinanceFuturesClient:
    """
    Thread-safe (per-instance) REST client for Binance USDT-M Futures.
    Uses a requests.Session with automatic retry on 5xx / network errors.
    """

    _ORDER_PATH = "/fapi/v1/order"
    _PING_PATH  = "/fapi/v1/ping"
    _TIME_PATH  = "/fapi/v1/time"

    def __init__(self, config: BotConfig) -> None:
        self._config  = config
        self._session = self._build_session()
        log.debug("BinanceFuturesClient initialised (base_url=%s)", config.base_url)

    # ── Public API ────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the testnet is reachable."""
        try:
            self._get(self._PING_PATH, signed=False)
            log.info("Testnet ping successful")
            return True
        except BinanceNetworkError as exc:
            log.warning("Testnet ping failed: %s", exc)
            return False

    def place_order(self, order: OrderRequest) -> OrderResponse:
        """
        Send a new-order request to Binance and return a parsed OrderResponse.
        All exceptions propagate to the caller (CLI layer catches them).
        """
        params = order.to_api_params()
        log.info("Placing order: %s", order.summary())
        log.debug("Order params: %s", params)

        raw = self._post(self._ORDER_PATH, params=params, signed=True)
        log.debug("Order raw response: %s", raw)

        response = OrderResponse.from_api(raw)
        log.info(
            "Order placed — id=%s status=%s executedQty=%s",
            response.order_id,
            response.status,
            response.executed_qty,
        )
        return response

    # ── Request helpers ───────────────────────────────────────────────────────

    def _get(self, path: str, *, signed: bool, params: dict | None = None) -> Any:
        url = self._config.base_url + path
        if signed:
            params = self._sign(params or {})
        log.debug("GET %s params=%s", url, params)
        return self._send("GET", url, params=params)

    def _post(self, path: str, *, params: dict, signed: bool) -> Any:
        url = self._config.base_url + path
        if signed:
            params = self._sign(params)
        log.debug("POST %s params=%s", url, params)
        return self._send("POST", url, params=params)

    def _send(self, method: str, url: str, *, params: dict | None = None) -> Any:
        headers = {"X-MBX-APIKEY": self._config.api_key}
        try:
            resp = self._session.request(
                method,
                url,
                params=params,
                headers=headers,
                timeout=10,
            )
        except requests.exceptions.Timeout as exc:
            raise BinanceNetworkError(f"Request timed out: {exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise BinanceNetworkError(f"Connection error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise BinanceNetworkError(f"Unexpected network error: {exc}") from exc

        log.debug(
            "HTTP %s %s → %s (%.0f ms)",
            method,
            url,
            resp.status_code,
            resp.elapsed.total_seconds() * 1000,
        )

        return self._parse_response(resp)

    def _parse_response(self, resp: requests.Response) -> Any:
        try:
            data = resp.json()
        except ValueError:
            raise BinanceNetworkError(
                f"Non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}"
            )

        # Binance error payload: {"code": -XXXX, "msg": "..."}
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            code = int(data["code"])
            msg  = data.get("msg", "Unknown error")
            log.error("Binance API error %d: %s", code, msg)
            raise BinanceAPIError(code, msg)

        if not resp.ok:
            raise BinanceNetworkError(
                f"HTTP {resp.status_code}: {resp.text[:200]}"
            )

        return data

    # ── Signing ───────────────────────────────────────────────────────────────

    def _sign(self, params: dict) -> dict:
        params = dict(params)
        params["timestamp"]  = int(time.time() * 1000)
        params["recvWindow"] = self._config.recv_window

        query_string = urlencode(params)
        signature = hmac.new(
            self._config.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ── Session builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist={500, 502, 503, 504},
            allowed_methods={"GET", "POST"},
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://",  adapter)
        return session
