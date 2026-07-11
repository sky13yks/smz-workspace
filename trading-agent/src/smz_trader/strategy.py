"""コア・サテライト戦略(トレンドフィルタ付きモメンタム)。

- コア(70%): SPY>200日SMAのリスクオン時、コアETF群から12-1モメンタム最大の1本を保有。
  リスクオフ時は現金。
- サテライト(30%): リスクオン時、ホワイトリストから 12-1モメンタム上位N銘柄
  (200日SMA上抜け・モメンタム正のもの)を逆ボラティリティで配分。
- 判定は全て日足終値ベースの純関数。乱数・時刻依存なし(決定論リプレイ可能)。
"""

from __future__ import annotations

from .data import Bar, symbol_ccy
from .portfolio import Portfolio, equity_jpy, weights
from .risk import Order
from .signals import momentum, realized_vol_annual, sma


def closes_of(bars: list[Bar]) -> list[float]:
    return [b.close for b in bars]


def is_first_trading_day_of_month(ref_bars: list[Bar]) -> bool:
    """参照銘柄の最終バーがその月の最初の営業日か。"""
    if len(ref_bars) < 2:
        return False
    last, prev = ref_bars[-1].date, ref_bars[-2].date
    return last[:7] != prev[:7]  # YYYY-MM が変わった


def target_weights(data: dict[str, list[Bar]], cfg) -> tuple[dict[str, float], dict]:
    """目標ウェイトを計算。info には判断根拠を入れる(レポート/AIレビュー用)。"""
    info: dict = {"risk_on": False, "core_pick": None, "satellite": [], "notes": []}
    ref = data.get(cfg.trend_ref)
    if not ref:
        info["notes"].append(f"参照銘柄{cfg.trend_ref}のデータなし → 全額現金")
        return {}, info
    ref_closes = closes_of(ref)
    trend_sma = sma(ref_closes, cfg.trend_sma_days)
    if trend_sma is None:
        info["notes"].append("SMA計算に必要な履歴不足 → 全額現金")
        return {}, info
    risk_on = ref_closes[-1] > trend_sma
    info["risk_on"] = risk_on
    info["trend"] = {"ref": cfg.trend_ref, "close": ref_closes[-1],
                     "sma": round(trend_sma, 2)}
    if not risk_on:
        info["notes"].append(f"{cfg.trend_ref} < {cfg.trend_sma_days}日SMA → リスクオフ(全額現金)")
        return {}, info

    targets: dict[str, float] = {}

    # --- コア: モメンタム最大のETFを1本 ---
    best, best_mom = None, None
    for sym in cfg.core:
        bars = data.get(sym)
        if not bars:
            continue
        m = momentum(closes_of(bars), cfg.mom_lookback_days, cfg.mom_skip_days)
        if m is not None and (best_mom is None or m > best_mom):
            best, best_mom = sym, m
    if best is not None:
        targets[best] = cfg.core_weight
        info["core_pick"] = {"symbol": best, "momentum": round(best_mom, 4)}
    else:
        info["notes"].append("コアETFのモメンタム計算不可 → コアは現金")

    # --- サテライト: モメンタム上位N + 逆ボラ配分 ---
    candidates = []
    for sym in cfg.satellite:
        bars = data.get(sym)
        if not bars:
            continue
        closes = closes_of(bars)
        m = momentum(closes, cfg.mom_lookback_days, cfg.mom_skip_days)
        s = sma(closes, cfg.trend_sma_days)
        v = realized_vol_annual(closes, cfg.vol_lookback_days)
        if m is None or s is None or v is None or v <= 0:
            continue
        if m > 0 and closes[-1] > s:
            candidates.append((sym, m, v))
    candidates.sort(key=lambda x: x[1], reverse=True)
    picks = candidates[: cfg.satellite_top_n]
    if picks:
        raw = {sym: min(cfg.vol_target_annual / v, 2.0) for sym, _, v in picks}
        total_raw = sum(raw.values())
        for sym, m, v in picks:
            w = raw[sym] / total_raw * cfg.satellite_weight
            w = min(w, cfg.max_weight_per_name)
            targets[sym] = w
            info["satellite"].append({"symbol": sym, "momentum": round(m, 4),
                                      "vol": round(v, 4), "weight": round(w, 4)})
    else:
        info["notes"].append("サテライト条件を満たす銘柄なし → サテライトは現金")
    return targets, info


def rebalance_orders(targets: dict[str, float], pf: Portfolio,
                     prices: dict[str, float], fx: float, cfg) -> list[Order]:
    """現状ウェイトと目標の乖離から注文リストを作る(バンド内はスキップ)。"""
    eq = equity_jpy(pf, prices, fx)
    if eq <= 0:
        return []
    cur = weights(pf, prices, fx)
    orders: list[Order] = []
    symbols = set(targets) | set(cur)
    for sym in sorted(symbols):
        px = prices.get(sym)
        if px is None or px <= 0:
            continue
        tw = targets.get(sym, 0.0)
        cw = cur.get(sym, 0.0)
        diff = tw - cw
        # バンド判定: 目標ゼロ(全売却)は必ず実行、それ以外は相対乖離で判断
        if tw > 0 and abs(diff) < cfg.band * tw:
            continue
        delta_jpy = diff * eq
        rate = fx if symbol_ccy(sym) == "USD" else 1.0
        qty = abs(delta_jpy) / (px * rate)
        if cfg.fractional:
            qty = round(qty, 4)
        else:
            qty = float(int(qty))
        if qty <= 0:
            continue
        side = "BUY" if diff > 0 else "SELL"
        if side == "SELL":
            qty = min(qty, pf.position_qty(sym))
            if qty <= 0:
                continue
        orders.append(Order(symbol=sym, side=side, qty=qty, est_price=px,
                            reason=f"rebalance: {cw:.1%}→{tw:.1%}"))

    # 買付合計が「売却後の現金×(1-バッファ-想定コスト)」を超える場合は比例縮小する
    # (目標ウェイト合計が100%だと現金バッファと必ず衝突するため)
    sells_jpy = sum(o.notional_jpy(fx) for o in orders if o.side == "SELL")
    buys_jpy = sum(o.notional_jpy(fx) for o in orders if o.side == "BUY")
    cost_margin = (cfg.slippage_bps + cfg.commission_bps) / 10_000.0
    budget = (pf.cash_jpy + sells_jpy) * (1.0 - cfg.cash_buffer - cost_margin)
    if buys_jpy > budget > 0:
        scale = budget / buys_jpy
        scaled: list[Order] = []
        for o in orders:
            if o.side == "BUY":
                q = round(o.qty * scale, 4) if cfg.fractional else float(int(o.qty * scale))
                if q <= 0:
                    continue
                scaled.append(Order(symbol=o.symbol, side=o.side, qty=q,
                                    est_price=o.est_price, reason=o.reason))
            else:
                scaled.append(o)
        orders = scaled
    return orders
