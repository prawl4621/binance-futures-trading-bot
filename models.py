"""
models.py — Validated, immutable order request and parsed API response.

No external dependencies required — pure stdlib dataclasses + Decimal for
exact numeric handling (Binance sends all quantities as strings anyway).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

from config import VALID_ORDER_TYPES, VALID_SIDES, VALID_SYMBOLS


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_decimal(value: str | float | int, field_name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"'{field_name}' must be a valid number, got: {value!r}")
    if d <= 0:
        raise ValueError(f"'{field_name}' must be > 0, got: {d}")
    return d


# ── Request model ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrderRequest:
    """
    Fully-validated representation of a user order request.

    Raises ValueError with a descriptive message on any invalid input so the
    CLI layer can surface it cleanly without catching broad exceptions.
    """
    symbol:     str
    side:       str
    order_type: str
    quantity:   Decimal
    price:      Optional[Decimal] = None

    # Binance requires LIMIT orders to specify a Time-In-Force.
    time_in_force: str = "GTC"

    def __post_init__(self) -> None:
        # Symbol
        sym = self.symbol.upper()
        if sym not in VALID_SYMBOLS:
            raise ValueError(
                f"Unsupported symbol '{sym}'. "
                f"Supported: {', '.join(sorted(VALID_SYMBOLS))}"
            )
        object.__setattr__(self, "symbol", sym)

        # Side
        side = self.side.upper()
        if side not in VALID_SIDES:
            raise ValueError(f"side must be one of {VALID_SIDES}, got: {side!r}")
        object.__setattr__(self, "side", side)

        # Order type
        otype = self.order_type.upper()
        if otype not in VALID_ORDER_TYPES:
            raise ValueError(
                f"order_type must be one of {VALID_ORDER_TYPES}, got: {otype!r}"
            )
        object.__setattr__(self, "order_type", otype)

        # Quantity — already converted by factory, but guard against raw usage
        if not isinstance(self.quantity, Decimal) or self.quantity <= 0:
            raise ValueError(f"quantity must be a positive number, got: {self.quantity!r}")

        # Price rules
        if otype == "LIMIT":
            if self.price is None:
                raise ValueError("price is required for LIMIT orders")
            if not isinstance(self.price, Decimal) or self.price <= 0:
                raise ValueError(f"price must be a positive number, got: {self.price!r}")
        elif otype == "MARKET" and self.price is not None:
            raise ValueError("price must not be provided for MARKET orders")

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_raw(
        cls,
        symbol:     str,
        side:       str,
        order_type: str,
        quantity:   str | float,
        price:      Optional[str | float] = None,
    ) -> "OrderRequest":
        """Construct and validate from raw CLI / string input."""
        qty   = _to_decimal(quantity, "quantity")
        prc   = _to_decimal(price, "price") if price is not None else None
        return cls(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=qty,
            price=prc,
        )

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_api_params(self) -> dict:
        """Return a dict ready to pass directly to the Binance REST endpoint."""
        params: dict = {
            "symbol":   self.symbol,
            "side":     self.side,
            "type":     self.order_type,
            "quantity": str(self.quantity),
        }
        if self.order_type == "LIMIT":
            params["price"]       = str(self.price)
            params["timeInForce"] = self.time_in_force
        return params

    def summary(self) -> str:
        price_str = f"@ {self.price}" if self.price else "(market price)"
        return (
            f"{self.side} {self.quantity} {self.symbol} "
            f"[{self.order_type}] {price_str}"
        )


# ── Response model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class OrderResponse:
    """Parsed, display-ready representation of a Binance order response."""
    order_id:     int
    client_order_id: str
    symbol:       str
    side:         str
    order_type:   str
    status:       str
    orig_qty:     str
    executed_qty: str
    avg_price:    str
    time_in_force: str
    raw:          dict   # keep the full payload for logging

    @classmethod
    def from_api(cls, data: dict) -> "OrderResponse":
        return cls(
            order_id       = data.get("orderId", 0),
            client_order_id= data.get("clientOrderId", ""),
            symbol         = data.get("symbol", ""),
            side           = data.get("side", ""),
            order_type     = data.get("type", ""),
            status         = data.get("status", ""),
            orig_qty       = data.get("origQty", "0"),
            executed_qty   = data.get("executedQty", "0"),
            avg_price      = data.get("avgPrice", "0"),
            time_in_force  = data.get("timeInForce", ""),
            raw            = data,
        )

    def display(self) -> str:
        lines = [
            "┌─── Order Response ─────────────────────────────────┐",
            f"│  Order ID      : {self.order_id}",
            f"│  Client OID    : {self.client_order_id}",
            f"│  Symbol        : {self.symbol}",
            f"│  Side          : {self.side}",
            f"│  Type          : {self.order_type}",
            f"│  Status        : {self.status}",
            f"│  Orig Qty      : {self.orig_qty}",
            f"│  Executed Qty  : {self.executed_qty}",
            f"│  Avg Price     : {self.avg_price}",
            f"│  Time-In-Force : {self.time_in_force or 'N/A'}",
            "└────────────────────────────────────────────────────┘",
        ]
        return "\n".join(lines)
