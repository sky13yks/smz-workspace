import tempfile
import unittest

from helpers import make_test_config, write_universe
from smz_trader.data import CsvDirProvider, fetch_all
from smz_trader.portfolio import Portfolio
from smz_trader.strategy import (is_first_trading_day_of_month,
                                 rebalance_orders, target_weights)


class TestStrategy(unittest.TestCase):
    def _load(self, spec):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        csv = tmp.name + "/csv"
        write_universe(csv, spec)
        cfg = make_test_config(tmp.name, csv)
        data = fetch_all(CsvDirProvider(csv), cfg.all_symbols)
        return cfg, data

    def test_risk_on_picks_uptrend(self):
        cfg, data = self._load({
            "SPY": (100, 0.0008), "QQQ": (100, 0.0012),
            "AAA": (50, 0.002), "BBB": (50, -0.002), "CCC": (50, 0.0005),
            "USDJPY": (150, 0.0)})
        targets, info = target_weights(data, cfg)
        self.assertTrue(info["risk_on"])
        # コアはモメンタム最大のQQQ
        self.assertIn("QQQ", targets)
        self.assertAlmostEqual(targets["QQQ"], cfg.core_weight)
        # 上昇トレンドのAAAは入り、下落のBBBは入らない
        self.assertIn("AAA", targets)
        self.assertNotIn("BBB", targets)
        # ウェイト合計は1以下
        self.assertLessEqual(sum(targets.values()), 1.0 + 1e-9)

    def test_risk_off_all_cash(self):
        cfg, data = self._load({
            "SPY": (100, -0.002), "QQQ": (100, -0.002),
            "AAA": (50, 0.002), "BBB": (50, 0.002), "CCC": (50, 0.002),
            "USDJPY": (150, 0.0)})
        targets, info = target_weights(data, cfg)
        self.assertFalse(info["risk_on"])
        self.assertEqual(targets, {})

    def test_orders_generated_and_band(self):
        cfg, data = self._load({
            "SPY": (100, 0.0008), "QQQ": (100, 0.0012),
            "AAA": (50, 0.002), "BBB": (50, -0.002), "CCC": (50, 0.0005),
            "USDJPY": (150, 0.0)})
        targets, _ = target_weights(data, cfg)
        prices = {s: b[-1].close for s, b in data.items()}
        fx = prices["USDJPY"]
        pf = Portfolio(cash_jpy=200_000)
        orders = rebalance_orders(targets, pf, prices, fx, cfg)
        self.assertTrue(all(o.side == "BUY" for o in orders))
        self.assertTrue(any(o.symbol == "QQQ" for o in orders))
        # 全部約定したと仮定して再度呼ぶと、バンド内なので注文ゼロになるはず
        for o in orders:
            pf.cash_jpy -= o.notional_jpy(fx)
            from smz_trader.portfolio import Position
            pos = pf.positions.setdefault(o.symbol, Position(o.symbol))
            pos.qty += o.qty
            pos.cost_jpy += o.notional_jpy(fx)
        orders2 = rebalance_orders(targets, pf, prices, fx, cfg)
        self.assertEqual(orders2, [])

    def test_first_trading_day(self):
        from smz_trader.data import Bar
        mk = lambda d: Bar(d, 1, 1, 1, 1, 0)
        self.assertTrue(is_first_trading_day_of_month([mk("2026-01-30"), mk("2026-02-02")]))
        self.assertFalse(is_first_trading_day_of_month([mk("2026-02-02"), mk("2026-02-03")]))


if __name__ == "__main__":
    unittest.main()
