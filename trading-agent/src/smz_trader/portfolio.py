"""台帳イベントからポートフォリオ状態を再構築する(決定論)。"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ledger
from .data import symbol_ccy


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    cost_jpy: float = 0.0  # 取得原価(手数料込み、円)


@dataclass
class Portfolio:
    cash_jpy: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    halted: bool = False
    halt_reason: str = ""
    total_deposits: float = 0.0
    total_withdrawals: float = 0.0

    def position_qty(self, symbol: str) -> float:
        p = self.positions.get(symbol)
        return p.qty if p else 0.0


def build_portfolio(events: list[dict]) -> Portfolio:
    pf = Portfolio()
    for e in events:
        t = e["type"]
        d = e["data"]
        if t == ledger.DEPOSIT:
            pf.cash_jpy += d["amount_jpy"]
            pf.total_deposits += d["amount_jpy"]
        elif t == ledger.WITHDRAW:
            pf.cash_jpy -= d["amount_jpy"]
            pf.total_withdrawals += d["amount_jpy"]
        elif t == ledger.FILL:
            sym = d["symbol"]
            pos = pf.positions.setdefault(sym, Position(symbol=sym))
            notional = d["notional_jpy"]
            fee = d.get("fee_jpy", 0.0)
            if d["side"] == "BUY":
                pf.cash_jpy -= notional + fee
                pos.qty += d["qty"]
                pos.cost_jpy += notional + fee
            else:  # SELL
                if pos.qty > 0:
                    ratio = min(d["qty"] / pos.qty, 1.0)
                    pos.cost_jpy *= (1.0 - ratio)
                pos.qty -= d["qty"]
                pf.cash_jpy += notional - fee
            if pos.qty <= 1e-9:
                pf.positions.pop(sym, None)
        elif t == ledger.HALT:
            pf.halted = True
            pf.halt_reason = d.get("reason", "")
        elif t == ledger.RESUME:
            pf.halted = False
            pf.halt_reason = ""
    return pf


def equity_jpy(pf: Portfolio, prices: dict[str, float], fx: float) -> float:
    """総資産評価額(円)。prices は銘柄→現地通貨建て終値。"""
    total = pf.cash_jpy
    for sym, pos in pf.positions.items():
        px = prices.get(sym)
        if px is None:
            continue
        rate = fx if symbol_ccy(sym) == "USD" else 1.0
        total += pos.qty * px * rate
    return total


def weights(pf: Portfolio, prices: dict[str, float], fx: float) -> dict[str, float]:
    eq = equity_jpy(pf, prices, fx)
    if eq <= 0:
        return {}
    out = {}
    for sym, pos in pf.positions.items():
        px = prices.get(sym)
        if px is None:
            continue
        rate = fx if symbol_ccy(sym) == "USD" else 1.0
        out[sym] = pos.qty * px * rate / eq
    return out


def marks(events: list[dict]) -> list[dict]:
    return [e["data"] for e in events if e["type"] == ledger.MARK]


def last_mark(events: list[dict]) -> dict | None:
    ms = marks(events)
    return ms[-1] if ms else None


def flows_since_last_mark(events: list[dict]) -> float:
    """直近MARK以降の純入出金(入金プラス)。TWR計算用。"""
    total = 0.0
    for e in reversed(events):
        if e["type"] == ledger.MARK:
            break
        if e["type"] == ledger.DEPOSIT:
            total += e["data"]["amount_jpy"]
        elif e["type"] == ledger.WITHDRAW:
            total -= e["data"]["amount_jpy"]
    return total


def compute_twr_index(events: list[dict], equity_now: float,
                      flows_now: float) -> float:
    """時間加重リターン指数を更新する。

    入出金の影響を除いた運用成績の指数(開始=1.0)。
    r = (E1 - F) / E0 として index *= (1+r)。
    """
    lm = last_mark(events)
    if lm is None or lm.get("equity_jpy", 0) <= 0:
        return 1.0
    prev_eq = lm["equity_jpy"]
    prev_idx = lm.get("twr_index", 1.0)
    r = (equity_now - flows_now) / prev_eq - 1.0
    return prev_idx * (1.0 + r)
