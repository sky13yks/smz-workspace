"""コマンドラインインターフェース。

使い方: smz-trader <command>  または  PYTHONPATH=src python3 -m smz_trader <command>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import ledger
from .config import load_config
from .portfolio import build_portfolio


def _default_config() -> str:
    # カレント → パッケージ隣接 の順で config/config.toml を探す
    for base in (Path.cwd(), Path(__file__).resolve().parents[2]):
        p = base / "config" / "config.toml"
        if p.exists():
            return str(p)
    return "config/config.toml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="smz-trader",
                                     description="SMZ Trader — システマティック株式運用エージェント")
    parser.add_argument("--config", default=_default_config(), help="config.tomlのパス")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="現在の状態を表示")
    p = sub.add_parser("deposit", help="入金を記録")
    p.add_argument("amount", type=float)
    p.add_argument("--note", default="")
    p = sub.add_parser("withdraw", help="出金を記録(現金不足なら売却プランを提示)")
    p.add_argument("amount", type=float)
    p.add_argument("--note", default="")
    p.add_argument("--execute-sells", action="store_true",
                   help="不足分の売却をペーパー約定してから出金する")
    p = sub.add_parser("run-daily", help="日次サイクルを実行")
    p.add_argument("--dry", action="store_true", help="台帳に書き込まない")
    p.add_argument("--offline", action="store_true", help="キャッシュのみ使用")
    p.add_argument("--force-rebalance", action="store_true", help="月初でなくてもリバランス")
    p = sub.add_parser("backtest", help="バックテストを実行")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--cash", type=float, default=200_000)
    p.add_argument("--offline", action="store_true")
    sub.add_parser("report", help="最新レポートのパスを表示")
    p = sub.add_parser("halt", help="手動で停止する")
    p.add_argument("--reason", default="manual")
    p = sub.add_parser("resume", help="停止から再開する")
    p.add_argument("--acknowledge", action="store_true",
                   help="ハードフロア停止からの再開に必須(リスク了承の明示)")
    sub.add_parser("verify-ledger", help="台帳のハッシュ連鎖を検証")
    sub.add_parser("fetch-data", help="全銘柄のデータをキャッシュに取得")

    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    state_dir = cfg.state_dir
    state_dir.mkdir(parents=True, exist_ok=True)

    if args.cmd == "status":
        events = ledger.read_events(state_dir)
        pf = build_portfolio(events)
        prices, fx = _try_prices(cfg)
        from .report import status_text
        print(status_text(cfg, pf, prices, fx))
        lm = [e for e in events if e["type"] == ledger.MARK]
        if lm:
            m = lm[-1]["data"]
            print(f"最終評価日  : {m['date']} (TWR指数 {m.get('twr_index', 1):.4f}, "
                  f"DD -{m.get('drawdown', 0):.1%})")
        return 0

    if args.cmd == "deposit":
        ledger.append_event(state_dir, ledger.DEPOSIT,
                            {"amount_jpy": args.amount, "note": args.note})
        print(f"入金 {args.amount:,.0f}円 を記録しました")
        return 0

    if args.cmd == "withdraw":
        return _withdraw(cfg, args)

    if args.cmd == "run-daily":
        from .runner import run_daily
        s = run_daily(cfg, dry=args.dry, offline=args.offline,
                      force_rebalance=args.force_rebalance)
        _print_summary(s)
        return 0 if s.status in ("ok", "already_done", "halted") else 1

    if args.cmd == "backtest":
        from .backtest import format_result, run_backtest
        from .data import fetch_all, make_provider
        provider = make_provider(cfg, offline=args.offline)
        data = fetch_all(provider, cfg.all_symbols)
        res = run_backtest(cfg, data, args.start, args.end, args.cash)
        print(format_result(res))
        out = state_dir / "backtests"
        out.mkdir(parents=True, exist_ok=True)
        csv = out / f"bt_{args.start}_{args.end}.csv"
        csv.write_text("date,equity_jpy,twr_index\n" + "\n".join(
            f"{d},{e},{i}" for d, e, i in res.equity_curve))
        print(f"エクイティカーブ: {csv}")
        return 0

    if args.cmd == "report":
        rep_dir = state_dir / "reports"
        reports = sorted(rep_dir.glob("daily_*.md")) if rep_dir.exists() else []
        if reports:
            print(reports[-1])
            print()
            print(reports[-1].read_text())
        else:
            print("レポートはまだありません(run-daily 実行後に生成されます)")
        return 0

    if args.cmd == "halt":
        ledger.append_event(state_dir, ledger.HALT,
                            {"reason": args.reason, "breaker": "manual"})
        print("停止しました(新規売買は行われません)")
        return 0

    if args.cmd == "resume":
        events = ledger.read_events(state_dir)
        halts = [e for e in events if e["type"] == ledger.HALT]
        if halts and halts[-1]["data"].get("breaker") == "hard_floor" and not args.acknowledge:
            print("ハードフロア(資産下限)による停止です。docs/00_master_plan.md の"
                  "「フロア到達時の手順」を読み、--acknowledge を付けて再開してください。")
            return 1
        ledger.append_event(state_dir, ledger.RESUME, {"note": "manual resume"})
        print("再開しました(次回 run-daily から売買が有効)")
        return 0

    if args.cmd == "verify-ledger":
        events = ledger.read_events(state_dir)
        ok, msg = ledger.verify_chain(events)
        print(("✓ " if ok else "✗ ") + msg)
        return 0 if ok else 1

    if args.cmd == "fetch-data":
        from .data import fetch_all, make_provider
        provider = make_provider(cfg)
        data = fetch_all(provider, cfg.all_symbols)
        for sym, bars in sorted(data.items()):
            print(f"  {sym:<8} {len(bars):>6}本  最終 {bars[-1].date}")
        return 0

    parser.error("unknown command")
    return 2


def _try_prices(cfg):
    """statusコマンド用に価格取得を試みる(オフラインならキャッシュ、失敗はNone)。"""
    try:
        from .data import fetch_all, make_provider
        provider = make_provider(cfg, offline=False)
        data = fetch_all(provider, cfg.all_symbols)
        prices = {s: b[-1].close for s, b in data.items()}
        return prices, prices.get(cfg.fx, 0.0)
    except Exception:
        return None, 0.0


def _withdraw(cfg, args) -> int:
    from .broker import PaperBroker
    from .runner import plan_withdrawal
    state_dir = cfg.state_dir
    events = ledger.read_events(state_dir)
    pf = build_portfolio(events)
    if args.amount <= 0:
        print("出金額は正の値で指定してください")
        return 1
    if pf.cash_jpy >= args.amount:
        ledger.append_event(state_dir, ledger.WITHDRAW,
                            {"amount_jpy": args.amount, "note": args.note})
        print(f"出金 {args.amount:,.0f}円 を記録しました(残現金 {pf.cash_jpy - args.amount:,.0f}円)")
        return 0
    prices, fx = _try_prices(cfg)
    if not prices or fx <= 0:
        print(f"現金不足({pf.cash_jpy:,.0f}円)ですが価格取得に失敗したため売却プランを作れません。")
        return 1
    orders, note = plan_withdrawal(pf, args.amount, prices, fx)
    print(f"現金 {pf.cash_jpy:,.0f}円 < 出金額 {args.amount:,.0f}円 → 売却が必要です:")
    for o in orders:
        print(f"  SELL {o.symbol} x {o.qty}")
    if note:
        print(f"  ⚠ {note}")
    if not args.execute_sells:
        print("実行するには --execute-sells を付けてください")
        return 0
    broker = PaperBroker(cfg)
    date = max(m["data"]["date"] for m in events if m["type"] == ledger.MARK) \
        if any(e["type"] == ledger.MARK for e in events) else "manual"
    fills, rejects = broker.execute(orders, prices, fx, pf.cash_jpy, date)
    from .runner import _fill_data
    for f in fills:
        ledger.append_event(state_dir, ledger.FILL, _fill_data(f))
    pf2 = build_portfolio(ledger.read_events(state_dir))
    amount = min(args.amount, pf2.cash_jpy)
    ledger.append_event(state_dir, ledger.WITHDRAW,
                        {"amount_jpy": amount, "note": args.note})
    print(f"売却{len(fills)}件を約定し、{amount:,.0f}円 の出金を記録しました")
    return 0


def _print_summary(s) -> None:
    print(f"[{s.date}] status={s.status} 総資産={s.equity_jpy:,.0f}円 "
          f"TWR={s.twr_index:.4f} DD=-{s.drawdown:.1%}")
    for f in s.fills:
        print(f"  約定: {f.side} {f.symbol} x {f.qty} @ {f.price:.2f}{f.ccy} "
              f"({f.notional_jpy:,.0f}円)")
    for sym, side, reason in s.rejected:
        print(f"  拒否: {side} {sym} — {reason}")
    if s.ai_memo:
        print(f"  AI: {s.ai_memo[:200]}")
    for n in s.notes:
        print(f"  注記: {n}")


if __name__ == "__main__":
    sys.exit(main())
