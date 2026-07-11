"""バックテスト/リプレイエンジン。

run_daily と同じ戦略・リスク・約定コードを日次で回す。乱数なし・時刻依存なしの
ため同一入力なら常に同一結果(= ペーパー口座は価格履歴から完全再構築できる)。

注意: config の satellite は「現在の」銘柄リストであり、過去に遡ると
生存者バイアスで成績が過大評価される。結果は絶対値でなく相対比較に使うこと。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .broker import PaperBroker
from .data import Bar
from .portfolio import Portfolio, Position, equity_jpy, weights
from .risk import check_breakers, liquidation_orders, validate_orders
from .signals import drawdown_from_peak
from .strategy import rebalance_orders, target_weights


@dataclass
class BacktestResult:
    start: str = ""
    end: str = ""
    start_cash: float = 0.0
    final_equity: float = 0.0
    twr_index: float = 1.0
    cagr: float = 0.0
    ann_vol: float = 0.0
    max_dd: float = 0.0
    n_fills: int = 0
    total_fees: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    equity_curve: list[tuple[str, float, float]] = field(default_factory=list)  # (date, equity, index)
    fills: list = field(default_factory=list)


def _slice_until(bars: list[Bar], date: str) -> list[Bar]:
    return [b for b in bars if b.date <= date]


def run_backtest(cfg, data: dict[str, list[Bar]], start: str, end: str,
                 start_cash: float) -> BacktestResult:
    res = BacktestResult(start=start, end=end, start_cash=start_cash)
    ref_all = data[cfg.trend_ref]
    dates = [b.date for b in ref_all if start <= b.date <= end]
    if not dates:
        raise ValueError("期間内に参照銘柄のデータがありません")

    pf = Portfolio(cash_jpy=start_cash, total_deposits=start_cash)
    broker = PaperBroker(cfg)
    index = 1.0
    prev_eq = start_cash
    index_series: list[float] = []
    daily_rets: list[float] = []
    month_start_idx: dict[str, float] = {}

    for today in dates:
        view = {sym: _slice_until(bars, today) for sym, bars in data.items()}
        view = {sym: bars for sym, bars in view.items() if bars}
        prices = {sym: bars[-1].close for sym, bars in view.items()}
        fx = prices.get(cfg.fx, 0.0)
        if fx <= 0:
            continue
        eq = equity_jpy(pf, prices, fx)
        if prev_eq > 0:
            r = eq / prev_eq - 1.0
            index *= (1.0 + r)
            daily_rets.append(r)
        prev_eq = eq
        index_series.append(index)
        month = today[:7]
        month_start_idx.setdefault(month, index)
        res.equity_curve.append((today, round(eq, 2), round(index, 6)))

        # ブレーカー
        br = check_breakers(index_series, eq, month_start_idx.get(month), cfg)
        if br.triggered and not pf.halted:
            fills, _ = broker.execute(liquidation_orders(pf, prices), prices, fx,
                                      pf.cash_jpy, today)
            _apply_fills(pf, fills)
            res.fills += fills
            pf.halted = True
            pf.halt_reason = f"{br.name}: {br.detail}"
            continue
        if pf.halted:
            continue

        # 月初リバランス
        ref_view = view[cfg.trend_ref]
        if len(ref_view) >= 2 and ref_view[-1].date[:7] != ref_view[-2].date[:7]:
            targets, _info = target_weights(view, cfg)
            orders = rebalance_orders(targets, pf, prices, fx, cfg)
            approved, _rej = validate_orders(orders, pf, prices, fx, cfg)
            fills, _brej = broker.execute(approved, prices, fx, pf.cash_jpy, today)
            _apply_fills(pf, fills)
            res.fills += fills

    res.final_equity = prev_eq
    res.twr_index = index
    res.n_fills = len(res.fills)
    res.total_fees = round(sum(f.fee_jpy for f in res.fills), 2)
    res.max_dd = drawdown_from_peak([1.0]) if not index_series else _max_dd(index_series)
    res.halted = pf.halted
    res.halt_reason = pf.halt_reason
    years = max(len(index_series) / 252.0, 1e-9)
    res.cagr = index ** (1 / years) - 1 if index > 0 else -1.0
    if len(daily_rets) > 2:
        mean = sum(daily_rets) / len(daily_rets)
        var = sum((r - mean) ** 2 for r in daily_rets) / (len(daily_rets) - 1)
        res.ann_vol = math.sqrt(var) * math.sqrt(252)
    return res


def _max_dd(series: list[float]) -> float:
    peak, mdd = -math.inf, 0.0
    for v in series:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, 1.0 - v / peak)
    return mdd


def _apply_fills(pf: Portfolio, fills) -> None:
    for f in fills:
        pos = pf.positions.setdefault(f.symbol, Position(symbol=f.symbol))
        if f.side == "BUY":
            pf.cash_jpy -= f.notional_jpy + f.fee_jpy
            pos.qty += f.qty
            pos.cost_jpy += f.notional_jpy + f.fee_jpy
        else:
            if pos.qty > 0:
                pos.cost_jpy *= (1.0 - min(f.qty / pos.qty, 1.0))
            pos.qty -= f.qty
            pf.cash_jpy += f.notional_jpy - f.fee_jpy
        if pos.qty <= 1e-9:
            pf.positions.pop(f.symbol, None)


def format_result(res: BacktestResult) -> str:
    lines = [
        "=== バックテスト結果 ===",
        f"期間        : {res.start} 〜 {res.end}",
        f"開始資金    : {res.start_cash:,.0f}円",
        f"最終資産    : {res.final_equity:,.0f}円",
        f"TWR指数     : {res.twr_index:.4f}",
        f"年率リターン: {res.cagr:+.2%}",
        f"年率ボラ    : {res.ann_vol:.2%}",
        f"最大DD      : -{res.max_dd:.2%}",
        f"約定回数    : {res.n_fills} (手数料合計 {res.total_fees:,.0f}円)",
    ]
    if res.halted:
        lines.append(f"⚠ ブレーカー発動で停止: {res.halt_reason}")
    lines.append("※ 現在の銘柄リストでの過去検証は生存者バイアスを含む(過大評価)")
    return "\n".join(lines)
