"""リスクガードレール。

このモジュールの制約は戦略・AIより常に優先される。AIはここを変更できない。
ルール一覧と根拠は docs/02_risk_policy.md を参照。
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import symbol_ccy
from .portfolio import Portfolio, equity_jpy
from .signals import drawdown_from_peak


@dataclass
class Order:
    symbol: str
    side: str          # BUY | SELL
    qty: float
    est_price: float   # 現地通貨建て想定価格
    reason: str = ""

    def notional_jpy(self, fx: float) -> float:
        rate = fx if symbol_ccy(self.symbol) == "USD" else 1.0
        return self.qty * self.est_price * rate


def validate_orders(orders: list[Order], pf: Portfolio,
                    prices: dict[str, float], fx: float,
                    cfg) -> tuple[list[Order], list[tuple[Order, str]]]:
    """注文のハードチェック。違反注文は除外して理由を返す。

    - ホワイトリスト外の銘柄は拒否(AIの幻覚・設定ミス対策)
    - 空売り禁止: 売却数量は保有数量以下
    - 信用取引なし: 買付総額は現金×(1-バッファ)以下
    - 個別銘柄の上限ウェイト(サテライト)
    - 最小約定金額未満はスキップ
    """
    approved: list[Order] = []
    rejected: list[tuple[Order, str]] = []
    eq = equity_jpy(pf, prices, fx)
    cash_available = pf.cash_jpy * (1.0 - cfg.cash_buffer)
    tradable = cfg.tradable_symbols

    # 売り→買いの順で処理(売却代金を買付原資に含める)
    for o in sorted(orders, key=lambda x: 0 if x.side == "SELL" else 1):
        if o.symbol not in tradable:
            rejected.append((o, "ホワイトリスト外の銘柄"))
            continue
        if o.qty <= 0 or o.est_price <= 0:
            rejected.append((o, "数量/価格が不正"))
            continue
        notional = o.notional_jpy(fx)
        if notional < cfg.min_order_jpy:
            rejected.append((o, f"最小約定金額({cfg.min_order_jpy:,.0f}円)未満"))
            continue
        if o.side == "SELL":
            held = pf.position_qty(o.symbol)
            if o.qty > held + 1e-9:
                rejected.append((o, f"保有数量({held})を超える売却(空売り禁止)"))
                continue
            cash_available += notional  # 概算(手数料は僅少)
            approved.append(o)
        elif o.side == "BUY":
            if notional > cash_available:
                rejected.append((o, "現金不足(信用取引・借金は禁止)"))
                continue
            # 個別銘柄上限(サテライトのみ。コアETFはcore_weightまで許容)
            if o.symbol in cfg.satellite and eq > 0:
                cur_val = pf.position_qty(o.symbol) * o.est_price * (
                    fx if symbol_ccy(o.symbol) == "USD" else 1.0)
                new_w = (cur_val + notional) / eq
                if new_w > cfg.max_weight_per_name * 1.05:  # 丸め誤差の許容
                    rejected.append((o, f"個別銘柄上限({cfg.max_weight_per_name:.0%})超過"))
                    continue
            cash_available -= notional
            approved.append(o)
        else:
            rejected.append((o, f"不明なside: {o.side}"))
    return approved, rejected


@dataclass
class BreakerResult:
    triggered: bool
    name: str = ""
    detail: str = ""


def check_breakers(index_series: list[float], equity_now: float,
                   month_start_index: float | None, cfg) -> BreakerResult:
    """サーキットブレーカー判定。

    - hard_floor: 総資産がハードフロア未満 → 全停止(人間レビュー必須)
    - max_drawdown: TWR指数の高値からのDDが上限超え → 全売却+停止
    - monthly_loss: 月初からの損失が上限超え → 全売却+停止
    """
    if equity_now < cfg.hard_floor_jpy:
        return BreakerResult(True, "hard_floor",
                             f"総資産{equity_now:,.0f}円 < フロア{cfg.hard_floor_jpy:,.0f}円")
    if index_series:
        dd = drawdown_from_peak(index_series)
        if dd >= cfg.max_drawdown:
            return BreakerResult(True, "max_drawdown",
                                 f"高値からのドローダウン {dd:.1%} ≥ {cfg.max_drawdown:.0%}")
        if month_start_index and month_start_index > 0:
            m_loss = 1.0 - index_series[-1] / month_start_index
            if m_loss >= cfg.monthly_loss_limit:
                return BreakerResult(True, "monthly_loss",
                                     f"月初からの損失 {m_loss:.1%} ≥ {cfg.monthly_loss_limit:.0%}")
    return BreakerResult(False)


def liquidation_orders(pf: Portfolio, prices: dict[str, float]) -> list[Order]:
    """全ポジション売却注文(ブレーカー発動時)。"""
    orders = []
    for sym, pos in pf.positions.items():
        px = prices.get(sym)
        if px and pos.qty > 0:
            orders.append(Order(symbol=sym, side="SELL", qty=pos.qty,
                                est_price=px, reason="circuit_breaker_liquidation"))
    return orders
