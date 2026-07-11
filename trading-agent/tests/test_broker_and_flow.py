import tempfile
import unittest

from helpers import make_test_config, write_universe
from smz_trader import ledger
from smz_trader.broker import PaperBroker
from smz_trader.data import CsvDirProvider, fetch_all
from smz_trader.portfolio import Portfolio, Position, build_portfolio
from smz_trader.risk import Order
from smz_trader.runner import plan_withdrawal, run_daily


class TestPaperBroker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        csv = self.tmp.name + "/csv"
        write_universe(csv, {"SPY": (100, 0.0), "QQQ": (100, 0.0), "AAA": (50, 0.0),
                             "BBB": (50, 0.0), "CCC": (50, 0.0), "USDJPY": (150, 0.0)})
        self.cfg = make_test_config(self.tmp.name, csv)

    def tearDown(self):
        self.tmp.cleanup()

    def test_buy_fill_math(self):
        broker = PaperBroker(self.cfg)
        fills, rejects = broker.execute(
            [Order("SPY", "BUY", qty=1, est_price=100.0)],
            {"SPY": 100.0}, fx=150.0, cash_jpy=100_000, date="2026-01-05")
        self.assertEqual(len(fills), 1)
        f = fills[0]
        # スリッページ10bps: 100.10ドル、円換算 15015円、手数料5bps
        self.assertAlmostEqual(f.price, 100.10, places=4)
        self.assertAlmostEqual(f.notional_jpy, 15015.0, places=1)
        self.assertAlmostEqual(f.fee_jpy, 15015.0 * 0.0005, places=1)

    def test_insufficient_cash_rejected(self):
        broker = PaperBroker(self.cfg)
        fills, rejects = broker.execute(
            [Order("SPY", "BUY", qty=100, est_price=100.0)],
            {"SPY": 100.0}, fx=150.0, cash_jpy=10_000, date="2026-01-05")
        self.assertEqual(len(fills), 0)
        self.assertEqual(len(rejects), 1)


class TestWithdrawPlan(unittest.TestCase):
    def test_sells_lowest_momentum_first(self):
        pf = Portfolio(cash_jpy=10_000)
        pf.positions["AAA"] = Position("AAA", qty=10, cost_jpy=75_000)  # 7.5万円分
        pf.positions["BBB"] = Position("BBB", qty=10, cost_jpy=75_000)
        prices = {"AAA": 50.0, "BBB": 50.0}
        ranks = {"AAA": 0.30, "BBB": 0.05}  # BBBが低モメンタム → 先に売る
        orders, note = plan_withdrawal(pf, 40_000, prices, 150.0, ranks)
        self.assertGreaterEqual(len(orders), 1)
        self.assertEqual(orders[0].symbol, "BBB")
        self.assertEqual(note, "")

    def test_cash_sufficient_no_orders(self):
        pf = Portfolio(cash_jpy=100_000)
        orders, note = plan_withdrawal(pf, 40_000, {}, 150.0)
        self.assertEqual(orders, [])


class TestRunDaily(unittest.TestCase):
    def _setup(self, spec, **cfg_overrides):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv = tmp.name + "/csv"
        write_universe(csv, spec)
        cfg = make_test_config(tmp.name, csv, **cfg_overrides)
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        return cfg

    UPTREND = {"SPY": (100, 0.0008), "QQQ": (100, 0.0012), "AAA": (50, 0.002),
               "BBB": (50, -0.002), "CCC": (50, 0.0005), "USDJPY": (150, 0.0)}

    def test_empty_ledger_errors(self):
        cfg = self._setup(self.UPTREND)
        s = run_daily(cfg)
        self.assertEqual(s.status, "error")

    def test_mark_and_idempotent(self):
        cfg = self._setup(self.UPTREND)
        ledger.append_event(cfg.state_dir, ledger.DEPOSIT,
                            {"amount_jpy": 200000, "note": ""})
        s1 = run_daily(cfg)
        self.assertEqual(s1.status, "ok")
        self.assertGreater(s1.equity_jpy, 0)
        s2 = run_daily(cfg)
        self.assertEqual(s2.status, "already_done")
        events = ledger.read_events(cfg.state_dir)
        ok, msg = ledger.verify_chain(events)
        self.assertTrue(ok, msg)

    def test_force_rebalance_buys(self):
        cfg = self._setup(self.UPTREND)
        ledger.append_event(cfg.state_dir, ledger.DEPOSIT,
                            {"amount_jpy": 200000, "note": ""})
        s = run_daily(cfg, force_rebalance=True)
        self.assertEqual(s.status, "ok")
        self.assertTrue(s.rebalanced)
        self.assertGreater(len(s.fills), 0)
        pf = build_portfolio(ledger.read_events(cfg.state_dir))
        self.assertGreater(len(pf.positions), 0)
        self.assertGreaterEqual(pf.cash_jpy, 0)  # 借金なし

    def test_hard_floor_halts(self):
        cfg = self._setup(self.UPTREND, hard_floor_jpy=300_000)  # わざと高いフロア
        ledger.append_event(cfg.state_dir, ledger.DEPOSIT,
                            {"amount_jpy": 200000, "note": ""})
        s = run_daily(cfg)
        self.assertEqual(s.status, "breaker")
        pf = build_portfolio(ledger.read_events(cfg.state_dir))
        self.assertTrue(pf.halted)
        # 停止中は何もしない
        s2 = run_daily(cfg, force_rebalance=True)
        self.assertIn(s2.status, ("halted", "already_done"))


class TestBacktest(unittest.TestCase):
    def test_smoke_and_deterministic(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv = tmp.name + "/csv"
        write_universe(csv, TestRunDaily.UPTREND, n=400, start_date="2024-01-01")
        cfg = make_test_config(tmp.name, csv)
        data = fetch_all(CsvDirProvider(csv), cfg.all_symbols)
        from smz_trader.backtest import run_backtest
        r1 = run_backtest(cfg, data, "2024-06-01", "2025-06-01", 200_000)
        r2 = run_backtest(cfg, data, "2024-06-01", "2025-06-01", 200_000)
        self.assertGreater(r1.final_equity, 0)
        self.assertEqual(r1.final_equity, r2.final_equity)  # 決定論
        self.assertEqual(r1.n_fills, r2.n_fills)
        self.assertGreater(r1.n_fills, 0)
        self.assertGreater(len(r1.equity_curve), 100)


if __name__ == "__main__":
    unittest.main()
