"""ブローカー層。

PaperBroker: 終値+スリッページで約定させる仮想ブローカー(ペーパートレード/バックテスト共用)。
実ブローカー(Alpaca/kabuステーション)は Phase 2 でこのインターフェースに実装する。
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import symbol_ccy
from .risk import Order


@dataclass(frozen=True)
class Fill:
    date: str
    symbol: str
    side: str
    qty: float
    price: float      # 現地通貨建て約定価格(スリッページ込み)
    ccy: str
    fx: float         # 約定時のUSDJPY(JPY建ては1.0)
    fee_jpy: float
    notional_jpy: float
    reason: str = ""


class PaperBroker:
    """仮想約定エンジン。現金残高を超える買いは拒否(guardrailの二重チェック)。"""

    def __init__(self, cfg):
        self.cfg = cfg

    def execute(self, orders: list[Order], prices: dict[str, float], fx: float,
                cash_jpy: float, date: str) -> tuple[list[Fill], list[tuple[Order, str]]]:
        fills: list[Fill] = []
        rejects: list[tuple[Order, str]] = []
        cash = cash_jpy
        slip = self.cfg.slippage_bps / 10_000.0
        for o in sorted(orders, key=lambda x: 0 if x.side == "SELL" else 1):
            base_px = prices.get(o.symbol)
            if base_px is None or base_px <= 0:
                rejects.append((o, "価格なし"))
                continue
            px = base_px * (1 + slip) if o.side == "BUY" else base_px * (1 - slip)
            ccy = symbol_ccy(o.symbol)
            rate = fx if ccy == "USD" else 1.0
            notional = o.qty * px * rate
            fee = max(self.cfg.commission_min_jpy,
                      notional * self.cfg.commission_bps / 10_000.0)
            if o.side == "BUY":
                if notional + fee > cash + 1e-6:
                    rejects.append((o, f"現金不足({cash:,.0f}円 < {notional + fee:,.0f}円)"))
                    continue
                cash -= notional + fee
            else:
                cash += notional - fee
            fills.append(Fill(date=date, symbol=o.symbol, side=o.side, qty=o.qty,
                              price=round(px, 6), ccy=ccy, fx=rate, fee_jpy=round(fee, 2),
                              notional_jpy=round(notional, 2), reason=o.reason))
        return fills, rejects


class AlpacaBroker:
    """米国株の実弾ブローカー(Phase 2で実装)。設定手順は docs/03_broker_and_data_setup.md。"""

    def __init__(self, cfg):
        raise NotImplementedError(
            "実弾取引は未実装です。Phase 1(ペーパー3ヶ月)の合格が先です。"
            "docs/00_master_plan.md のゲート条件を参照。")


class KabuStationBroker:
    """日本株の実弾ブローカー(Phase 3で実装)。"""

    def __init__(self, cfg):
        raise NotImplementedError(
            "日本株の実弾取引は未実装です(Phase 3)。docs/03_broker_and_data_setup.md 参照。")


def make_broker(cfg):
    if cfg.trading == "paper":
        return PaperBroker(cfg)
    raise NotImplementedError(
        "mode.trading='live' はまだ有効化できません。Phase 2のゲート条件"
        "(docs/00_master_plan.md)を満たし、ブローカー実装を追加してください。")
