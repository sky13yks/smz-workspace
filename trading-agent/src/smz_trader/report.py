"""日次レポート(Markdown)と状態表示。"""

from __future__ import annotations

from pathlib import Path

from .data import symbol_ccy
from .portfolio import Portfolio, equity_jpy


def status_text(cfg, pf: Portfolio, prices: dict[str, float] | None = None,
                fx: float = 0.0) -> str:
    lines = ["=== SMZ Trader 状態 ==="]
    lines.append(f"モード      : {cfg.trading}")
    lines.append(f"現金        : {pf.cash_jpy:,.0f}円")
    lines.append(f"入金累計    : {pf.total_deposits:,.0f}円 / 出金累計: {pf.total_withdrawals:,.0f}円")
    if pf.halted:
        lines.append(f"⚠ 停止中    : {pf.halt_reason}")
    if pf.positions:
        lines.append("--- 保有ポジション ---")
        for sym, pos in sorted(pf.positions.items()):
            line = f"  {sym:<8} {pos.qty:>12.4f}株  取得原価 {pos.cost_jpy:>12,.0f}円"
            if prices and sym in prices and fx > 0:
                rate = fx if symbol_ccy(sym) == "USD" else 1.0
                val = pos.qty * prices[sym] * rate
                pnl = val - pos.cost_jpy
                line += f"  評価額 {val:>12,.0f}円 ({pnl:+,.0f}円)"
            lines.append(line)
    else:
        lines.append("保有ポジションなし(全額現金)")
    if prices and fx > 0:
        lines.append(f"総資産      : {equity_jpy(pf, prices, fx):,.0f}円 (USDJPY={fx:.2f})")
    return "\n".join(lines)


def write_daily_report(cfg, summary, pf: Portfolio,
                       prices: dict[str, float], fx: float) -> Path:
    rep_dir = cfg.state_dir / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    date = summary.date or "unknown"
    path = rep_dir / f"daily_{date}.md"

    eq = equity_jpy(pf, prices, fx)
    pnl_total = eq - (pf.total_deposits - pf.total_withdrawals)
    lines = [
        f"# 日次レポート {date}",
        "",
        f"- ステータス: **{summary.status}**" + (" (リバランス実行)" if summary.rebalanced else ""),
        f"- 総資産: **{eq:,.0f}円** (TWR指数 {summary.twr_index:.4f} / 高値からのDD -{summary.drawdown:.1%})",
        f"- 累計損益: {pnl_total:+,.0f}円 (純入金 {pf.total_deposits - pf.total_withdrawals:,.0f}円)",
        f"- 現金: {pf.cash_jpy:,.0f}円 (即時出金可能額の目安)",
        f"- USDJPY: {fx:.2f}",
        "",
    ]
    if pf.positions:
        lines.append("## 保有ポジション")
        lines.append("")
        lines.append("| 銘柄 | 数量 | 評価額(円) | ウェイト |")
        lines.append("|---|---:|---:|---:|")
        for sym, pos in sorted(pf.positions.items()):
            rate = fx if symbol_ccy(sym) == "USD" else 1.0
            px = prices.get(sym, 0.0)
            val = pos.qty * px * rate
            w = val / eq if eq > 0 else 0
            lines.append(f"| {sym} | {pos.qty:.4f} | {val:,.0f} | {w:.1%} |")
        lines.append("")
    if summary.fills:
        lines.append("## 本日の約定")
        lines.append("")
        lines.append("| 銘柄 | 売買 | 数量 | 価格 | 円換算 | 手数料 |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for f in summary.fills:
            lines.append(f"| {f.symbol} | {f.side} | {f.qty:.4f} | {f.price:.2f} {f.ccy} "
                         f"| {f.notional_jpy:,.0f} | {f.fee_jpy:,.0f} |")
        lines.append("")
    if summary.rejected:
        lines.append("## 拒否された注文(ガードレール)")
        lines.append("")
        for sym, side, reason in summary.rejected:
            lines.append(f"- {sym} {side}: {reason}")
        lines.append("")
    if summary.strategy_info:
        info = summary.strategy_info
        lines.append("## 戦略シグナル")
        lines.append("")
        lines.append(f"- リスク判定: {'リスクオン' if info.get('risk_on') else 'リスクオフ(現金退避)'}")
        if info.get("trend"):
            t = info["trend"]
            lines.append(f"- トレンド: {t['ref']} 終値 {t['close']:.2f} vs SMA {t['sma']:.2f}")
        if info.get("core_pick"):
            c = info["core_pick"]
            lines.append(f"- コア採用: {c['symbol']} (12-1モメンタム {c['momentum']:+.1%})")
        for sat in info.get("satellite", []):
            lines.append(f"- サテライト: {sat['symbol']} mom {sat['momentum']:+.1%} "
                         f"vol {sat['vol']:.0%} → w {sat['weight']:.1%}")
        lines.append("")
    if summary.ai_memo:
        lines.append("## AIレビュー所感")
        lines.append("")
        lines.append(summary.ai_memo)
        for a in summary.ai_applied:
            lines.append(f"- 適用: {a}")
        lines.append("")
    if summary.notes:
        lines.append("## 注記")
        lines.append("")
        for n in summary.notes:
            lines.append(f"- {n}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
