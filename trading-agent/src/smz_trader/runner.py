"""日次運用サイクルのオーケストレーション。

run_daily の流れ:
  台帳検証 → データ取得 → 評価(MARK) → ブレーカー判定 → (月初なら)リバランス
  → ガードレール → AIレビュー → 約定 → 台帳記録 → レポート
どこかで失敗したら「何もしない」がデフォルト(フェイルセーフ = 現金保持)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import advisor, ledger
from .broker import BrokerError, make_broker
from .config import Config
from .data import DataUnavailable, fetch_all, make_provider
from .portfolio import (build_portfolio, compute_twr_index, equity_jpy,
                        flows_since_last_mark, last_mark, marks, weights)
from .risk import check_breakers, liquidation_orders, validate_orders
from .signals import drawdown_from_peak
from .strategy import (is_first_trading_day_of_month, rebalance_orders,
                       target_weights)


@dataclass
class DailySummary:
    date: str = ""
    status: str = ""          # ok | halted | breaker | no_data | already_done | error
    equity_jpy: float = 0.0
    twr_index: float = 1.0
    drawdown: float = 0.0
    fills: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    ai_memo: str = ""
    ai_applied: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    strategy_info: dict = field(default_factory=dict)
    rebalanced: bool = False


def latest_prices(data: dict) -> dict[str, float]:
    return {sym: bars[-1].close for sym, bars in data.items() if bars}


def run_daily(cfg: Config, dry: bool = False, offline: bool = False,
              force_rebalance: bool = False) -> DailySummary:
    s = DailySummary()
    state_dir = cfg.state_dir

    # 1. 台帳の整合性検証
    events = ledger.read_events(state_dir)
    ok, msg = ledger.verify_chain(events)
    if not ok:
        s.status = "error"
        s.notes.append(f"台帳検証失敗: {msg} — 手動確認が必要です")
        return s
    if not events:
        s.status = "error"
        s.notes.append("台帳が空です。まず `smz-trader deposit 200000` で入金してください")
        return s

    pf = build_portfolio(events)

    # 2. データ取得(失敗したら何もしない)
    try:
        provider = make_provider(cfg, offline=offline)
        data = fetch_all(provider, cfg.all_symbols)
    except DataUnavailable as e:
        s.status = "no_data"
        s.notes.append(f"データ取得不能のため何もしません(フェイルセーフ): {e}")
        if not dry:
            ledger.append_event(state_dir, ledger.NOTE, {"text": s.notes[-1]})
        return s

    ref_bars = data[cfg.trend_ref]
    today = ref_bars[-1].date
    s.date = today
    prices = latest_prices(data)
    fx = prices.get(cfg.fx, 0.0)
    if fx <= 0:
        s.status = "no_data"
        s.notes.append(f"為替({cfg.fx})が取得できません")
        return s

    # ブローカーを早期に一度だけ生成(ライブ多重ゲートをここで検証)。
    # 失敗したら発注・清算のいずれも行わずフェイルセーフで停止する。
    try:
        broker = make_broker(cfg)
    except BrokerError as e:
        s.status = "error"
        s.notes.append(f"ブローカー利用不可のため何もしません(フェイルセーフ): {e}")
        if not dry:
            ledger.append_event(state_dir, ledger.NOTE, {"text": s.notes[-1]})
        return s

    # 3. 冪等性: 同じ日付のMARKが既にあればスキップ
    lm = last_mark(events)
    if lm and lm.get("date") == today and not dry and not force_rebalance:
        s.status = "already_done"
        s.equity_jpy = lm["equity_jpy"]
        s.twr_index = lm.get("twr_index", 1.0)
        s.notes.append(f"{today} は処理済み(新しいバーが来るまで待機)")
        return s

    # 4. 評価とTWR指数更新
    eq = equity_jpy(pf, prices, fx)
    flows = flows_since_last_mark(events)
    idx = compute_twr_index(events, eq, flows)
    index_series = [m.get("twr_index", 1.0) for m in marks(events)] + [idx]
    dd = drawdown_from_peak(index_series)
    s.equity_jpy, s.twr_index, s.drawdown = eq, idx, dd
    if not dry and not (lm and lm.get("date") == today):
        ledger.append_event(state_dir, ledger.MARK, {
            "date": today, "equity_jpy": round(eq, 2),
            "net_flow_jpy": round(flows, 2),
            "twr_index": round(idx, 6), "drawdown": round(dd, 4)})
        events = ledger.read_events(state_dir)

    # 5. サーキットブレーカー
    month_start_idx = _month_start_index(events, today)
    br = check_breakers(index_series, eq, month_start_idx, cfg)
    if br.triggered and not pf.halted:
        s.status = "breaker"
        s.notes.append(f"ブレーカー発動: {br.name} — {br.detail}")
        liq = liquidation_orders(pf, prices)
        fills, _ = broker.execute(liq, prices, fx, pf.cash_jpy, today)
        if not dry:
            for f in fills:
                ledger.append_event(state_dir, ledger.FILL, _fill_data(f))
            ledger.append_event(state_dir, ledger.HALT,
                                {"reason": br.detail, "breaker": br.name})
        s.fills = fills
        s.notes.append("全ポジションを売却して停止しました。再開は `smz-trader resume`")
        _write_report(cfg, s, pf, prices, fx, dry)
        return s

    if pf.halted:
        s.status = "halted"
        s.notes.append(f"停止中({pf.halt_reason})。`smz-trader resume` で再開")
        _write_report(cfg, s, pf, prices, fx, dry)
        return s

    # 6. リバランス(月初のみ)
    if force_rebalance or is_first_trading_day_of_month(ref_bars):
        s.rebalanced = True
        targets, info = target_weights(data, cfg)
        s.strategy_info = info
        orders = rebalance_orders(targets, pf, prices, fx, cfg)
        approved, rejected = validate_orders(orders, pf, prices, fx, cfg)
        s.rejected = [(o.symbol, o.side, reason) for o, reason in rejected]

        # AIレビュー(任意層。失敗してもルールベースで続行)
        if approved and cfg.ai_enabled:
            ctx = advisor.build_context(today, eq, dd, weights(pf, prices, fx),
                                        approved, info, fx)
            result = advisor.review(ctx, cfg)
            if result.available:
                approved, applied = advisor.apply_decisions(
                    approved, result, cfg.ai_veto_power)
                s.ai_memo = result.memo
                s.ai_applied = applied
                if not dry:
                    ledger.append_event(state_dir, ledger.AI_MEMO, {
                        "model": result.model, "memo": result.memo,
                        "decisions": result.decisions,
                        "applied": applied,
                        "prompt_sha256": result.prompt_sha256})
            else:
                s.notes.append(f"AIレビュー未実施: {result.skip_reason}")

        fills, broker_rejects = broker.execute(approved, prices, fx, pf.cash_jpy, today)
        s.rejected += [(o.symbol, o.side, r) for o, r in broker_rejects]
        s.fills = fills
        if not dry:
            for f in fills:
                ledger.append_event(state_dir, ledger.FILL, _fill_data(f))
    s.status = "ok"
    _write_report(cfg, s, build_portfolio(ledger.read_events(state_dir)) if not dry else pf,
                  prices, fx, dry)
    return s


def _month_start_index(events: list[dict], today: str) -> float | None:
    """当月最初のMARKのTWR指数。"""
    for m in marks(events):
        if m.get("date", "")[:7] == today[:7]:
            return m.get("twr_index", 1.0)
    return None


def _fill_data(f) -> dict:
    d = {"date": f.date, "symbol": f.symbol, "side": f.side, "qty": f.qty,
         "price": f.price, "ccy": f.ccy, "fx": f.fx, "fee_jpy": f.fee_jpy,
         "notional_jpy": f.notional_jpy, "reason": f.reason}
    # 実ブローカーの冪等キー(あれば記録。sync-fills の二重計上防止に使う)
    if getattr(f, "client_order_id", ""):
        d["client_order_id"] = f.client_order_id
    if getattr(f, "broker_order_id", ""):
        d["broker_order_id"] = f.broker_order_id
    return d


def _write_report(cfg, summary, pf, prices, fx, dry: bool):
    if dry:
        return
    from .report import write_daily_report
    try:
        write_daily_report(cfg, summary, pf, prices, fx)
    except OSError as e:
        summary.notes.append(f"レポート書き込み失敗: {e}")


def sync_fills(cfg: Config, offline: bool = False) -> list:
    """実ブローカー側で後刻約定した注文を台帳へ反映する(冪等)。

    市場閉場後に run-daily を実行すると成行注文は翌場寄りで約定する。その約定を
    client_order_id をキーに重複なく FILL として記録する。ペーパーでは何もしない。
    戻り値: 新たに記録した Fill のリスト。
    """
    from .broker import AlpacaBroker
    broker = make_broker(cfg)
    if not isinstance(broker, AlpacaBroker):
        return []
    state_dir = cfg.state_dir
    events = ledger.read_events(state_dir)
    recorded = {e["data"].get("client_order_id")
                for e in events if e["type"] == ledger.FILL and e["data"].get("client_order_id")}

    # notional(円)計算のため為替を取得。取れなければ何もしない(フェイルセーフ)。
    try:
        provider = make_provider(cfg, offline=offline)
        fx_bars = provider.history(cfg.fx)
        fx = fx_bars[-1].close if fx_bars else 0.0
    except DataUnavailable:
        fx = 0.0
    if fx <= 0:
        return []

    new_fills = []
    for od in broker.recent_orders("closed"):
        coid = od.get("client_order_id", "")
        if (od.get("status") == "filled" and coid.startswith("smz-")
                and coid not in recorded and float(od.get("filled_qty") or 0) > 0):
            f = broker._fill_from_order(od, None, fx, od.get("filled_at", "")[:10])
            ledger.append_event(state_dir, ledger.FILL, _fill_data(f))
            new_fills.append(f)
            recorded.add(coid)
    return new_fills


def reconcile(cfg: Config) -> dict:
    """台帳のポジション・現金と実ブローカーの実残高を照合する(読み取り専用)。

    戻り値: {positions: [{symbol, ledger_qty, broker_qty, diff}], account: {...}, notes: [...]}
    """
    from .broker import AlpacaBroker
    result: dict = {"positions": [], "account": {}, "notes": []}
    broker = make_broker(cfg)
    if not isinstance(broker, AlpacaBroker):
        result["notes"].append("ペーパーモード: 外部ブローカーとの照合はありません")
        return result
    pf = build_portfolio(ledger.read_events(cfg.state_dir))
    broker_pos = {p["symbol"]: float(p.get("qty") or 0.0) for p in broker.positions()}
    symbols = set(pf.positions) | set(broker_pos)
    for sym in sorted(symbols):
        lq = pf.position_qty(sym)
        bq = broker_pos.get(sym, 0.0)
        result["positions"].append({
            "symbol": sym, "ledger_qty": round(lq, 4),
            "broker_qty": round(bq, 4), "diff": round(bq - lq, 4)})
    acct = broker.account()
    result["account"] = {
        "status": acct.get("status"),
        "currency": acct.get("currency"),
        "cash": acct.get("cash"),
        "buying_power": acct.get("buying_power"),
        "ledger_cash_jpy": round(pf.cash_jpy, 0),
        "is_paper": broker.is_paper,
    }
    return result


def plan_withdrawal(pf, amount_jpy: float, prices: dict[str, float], fx: float,
                    momentum_ranks: dict[str, float] | None = None):
    """出金プラン: 現金が足りなければモメンタムが低い銘柄から売却する。

    戻り値: (売却注文リスト, 不足額メモ)
    """
    from .data import symbol_ccy
    from .risk import Order
    shortfall = amount_jpy - pf.cash_jpy
    orders: list[Order] = []
    if shortfall <= 0:
        return orders, ""
    ranks = momentum_ranks or {}
    holdings = sorted(pf.positions.values(),
                      key=lambda p: ranks.get(p.symbol, -999))  # 低モメンタム優先
    remaining = shortfall * 1.02  # 手数料・スリッページの余裕
    for pos in holdings:
        if remaining <= 0:
            break
        px = prices.get(pos.symbol)
        if not px:
            continue
        rate = fx if symbol_ccy(pos.symbol) == "USD" else 1.0
        val = pos.qty * px * rate
        sell_val = min(val, remaining)
        qty = round(sell_val / (px * rate), 4)
        if qty > 0:
            orders.append(Order(symbol=pos.symbol, side="SELL", qty=min(qty, pos.qty),
                                est_price=px, reason=f"withdrawal_{amount_jpy:.0f}"))
            remaining -= sell_val
    note = "" if remaining <= 0 else f"全売却でも{remaining:,.0f}円不足(出金額が総資産超過)"
    return orders, note
