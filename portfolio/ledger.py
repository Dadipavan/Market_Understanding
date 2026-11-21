"""Paper-trading ledger: cash, holdings (average cost), realised P&L, journal.
Lives in the user's session and is exported/imported as JSON, so a hosted app
never stores anyone's portfolio on the server."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from risk.costs import trade_costs


@dataclass
class Ledger:
    starting_cash: float = 1_000_000.0
    trades: list[dict] = field(default_factory=list)

    # ---- derived state (always recomputed from trades: single source of truth)
    def state(self) -> tuple[float, dict]:
        cash, hold = self.starting_cash, {}
        for t in self.trades:
            cash, hold = self._apply(cash, hold, t)
        return cash, hold

    @staticmethod
    def _apply(cash: float, hold: dict, t: dict) -> tuple[float, dict]:
        sym, qty, px, fee = t["symbol"], int(t["qty"]), float(t["price"]), float(t.get("fees", 0.0))
        h = hold.setdefault(sym, {"qty": 0, "avg": 0.0})
        if t["side"] == "buy":
            cost = qty * px + fee
            if cost > cash + 1e-6:
                raise ValueError(f"Not enough cash: need {cost:,.2f}, have {cash:,.2f}.")
            h["avg"] = (h["avg"] * h["qty"] + qty * px) / (h["qty"] + qty) if h["qty"] + qty else 0.0
            h["qty"] += qty
            cash -= cost
        elif t["side"] == "sell":
            if qty > h["qty"]:
                raise ValueError(f"Cannot sell {qty} {sym}: you hold {h['qty']}.")
            h["qty"] -= qty
            cash += qty * px - fee
            if h["qty"] == 0:
                h["avg"] = 0.0
        else:
            raise ValueError("side must be 'buy' or 'sell'")
        if h["qty"] == 0:
            hold.pop(sym, None)
        return cash, hold

    def add_trade(self, date, symbol: str, side: str, qty: int, price: float, kind: str = "delivery",
                  stop: float | None = None, target: float | None = None, note: str = "") -> dict:
        if qty <= 0 or price <= 0:
            raise ValueError("Quantity and price must be positive.")
        fee = trade_costs(price, qty, side, kind)
        t = {"date": str(pd.Timestamp(date).date()), "symbol": symbol.upper(), "side": side, "qty": int(qty),
             "price": float(price), "fees": fee, "stop": stop, "target": target, "note": note}
        cash, hold = self.state()
        # realised P&L for sells (average cost method)
        if side == "sell":
            avg = hold.get(t["symbol"], {}).get("avg", 0.0)
            t["realised"] = round((price - avg) * qty - fee, 2)
        self._apply(cash, {k: dict(v) for k, v in hold.items()}, t)  # validates; raises on error
        self.trades.append(t)
        return t

    # ---- analytics
    def holdings_table(self, prices: dict[str, float]) -> pd.DataFrame:
        _, hold = self.state()
        rows = []
        for sym, h in hold.items():
            px = prices.get(sym)
            val = h["qty"] * px if px else None
            rows.append({"symbol": sym, "qty": h["qty"], "avg_cost": round(h["avg"], 2), "price": px,
                         "value": round(val, 2) if val else None,
                         "unrealised": round((px - h["avg"]) * h["qty"], 2) if px else None,
                         "unrealised_pct": round((px / h["avg"] - 1) * 100, 2) if px and h["avg"] else None})
        return pd.DataFrame(rows, columns=["symbol", "qty", "avg_cost", "price", "value", "unrealised", "unrealised_pct"])

    def summary(self, prices: dict[str, float]) -> dict:
        cash, hold = self.state()
        value = sum(h["qty"] * prices.get(s, h["avg"]) for s, h in hold.items())
        sells = [t for t in self.trades if t["side"] == "sell"]
        realised = sum(t.get("realised", 0.0) for t in sells)
        wins = [t["realised"] for t in sells if t.get("realised", 0) > 0]
        losses = [t["realised"] for t in sells if t.get("realised", 0) <= 0]
        n = len(sells)
        equity = cash + value
        return {
            "cash": round(cash, 2), "holdings_value": round(value, 2), "equity": round(equity, 2),
            "total_return_pct": round((equity / self.starting_cash - 1) * 100, 2),
            "realised_pnl": round(realised, 2), "fees_paid": round(sum(t["fees"] for t in self.trades), 2),
            "closed_trades": n, "win_rate": (len(wins) / n) if n else 0.0,
            "avg_win": (sum(wins) / len(wins)) if wins else 0.0, "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
            "expectancy": (realised / n) if n else 0.0,
            "concentration_pct": round(max((h["qty"] * prices.get(s, h["avg"]) for s, h in hold.items()), default=0) / equity * 100, 1) if equity else 0.0,
        }

    def to_json(self) -> str:
        return json.dumps({"starting_cash": self.starting_cash, "trades": self.trades}, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Ledger":
        d = json.loads(text)
        led = cls(starting_cash=float(d["starting_cash"]))
        cash, hold = led.starting_cash, {}
        for t in d["trades"]:
            cash, hold = cls._apply(cash, hold, t)   # validates the whole history
            led.trades.append(t)
        return led

    def trades_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.trades)
