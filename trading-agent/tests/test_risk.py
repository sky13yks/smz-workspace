import tempfile
import unittest

from helpers import make_test_config, write_universe
from smz_trader.portfolio import Portfolio, Position
from smz_trader.risk import Order, check_breakers, validate_orders


class TestGuardrails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        csv = self.tmp.name + "/csv"
        write_universe(csv, {"SPY": (100, 0.0005), "QQQ": (100, 0.0006),
                             "AAA": (50, 0.001), "BBB": (50, -0.001),
                             "CCC": (50, 0.0), "USDJPY": (150, 0.0)})
        self.cfg = make_test_config(self.tmp.name, csv)
        self.prices = {"SPY": 100.0, "AAA": 50.0, "BBB": 50.0}
        self.fx = 150.0

    def tearDown(self):
        self.tmp.cleanup()

    def test_reject_over_cash(self):
        pf = Portfolio(cash_jpy=10_000)
        orders = [Order("SPY", "BUY", qty=10, est_price=100.0)]  # 15万円分
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 0)
        self.assertIn("現金不足", rejected[0][1])

    def test_reject_short_sell(self):
        pf = Portfolio(cash_jpy=100_000)
        orders = [Order("SPY", "SELL", qty=1, est_price=100.0)]
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 0)
        self.assertIn("空売り", rejected[0][1])

    def test_reject_non_whitelist(self):
        pf = Portfolio(cash_jpy=100_000)
        orders = [Order("EVIL", "BUY", qty=1, est_price=10.0)]
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 0)
        self.assertIn("ホワイトリスト", rejected[0][1])

    def test_reject_over_name_cap(self):
        # 総資産100万円、AAA(サテライト)上限20% → 30万円の買いは拒否
        pf = Portfolio(cash_jpy=1_000_000)
        orders = [Order("AAA", "BUY", qty=40, est_price=50.0)]  # 30万円
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 0)
        self.assertIn("個別銘柄上限", rejected[0][1])

    def test_sell_frees_cash_for_buy(self):
        pf = Portfolio(cash_jpy=1_000)
        pf.positions["AAA"] = Position("AAA", qty=10, cost_jpy=75_000)
        orders = [Order("SPY", "BUY", qty=4, est_price=100.0),   # 6万円
                  Order("AAA", "SELL", qty=10, est_price=50.0)]  # 7.5万円入金
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 2, rejected)

    def test_min_order_skip(self):
        pf = Portfolio(cash_jpy=100_000)
        orders = [Order("SPY", "BUY", qty=0.00001, est_price=100.0)]
        approved, rejected = validate_orders(orders, pf, self.prices, self.fx, self.cfg)
        self.assertEqual(len(approved), 0)
        self.assertIn("最小約定金額", rejected[0][1])


class TestBreakers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        csv = self.tmp.name + "/csv"
        write_universe(csv, {"SPY": (100, 0.0), "QQQ": (100, 0.0),
                             "AAA": (50, 0.0), "BBB": (50, 0.0), "CCC": (50, 0.0),
                             "USDJPY": (150, 0.0)})
        self.cfg = make_test_config(self.tmp.name, csv)

    def tearDown(self):
        self.tmp.cleanup()

    def test_max_drawdown_trigger(self):
        series = [1.0, 1.1, 0.82]  # 高値1.1から-25.5%
        br = check_breakers(series, equity_now=160_000, month_start_index=1.0,
                            cfg=self.cfg)
        self.assertTrue(br.triggered)
        self.assertEqual(br.name, "max_drawdown")

    def test_monthly_loss_trigger(self):
        series = [1.0, 1.02, 0.9]
        br = check_breakers(series, equity_now=180_000, month_start_index=1.02,
                            cfg=self.cfg)
        self.assertTrue(br.triggered)
        self.assertEqual(br.name, "monthly_loss")

    def test_hard_floor_trigger(self):
        br = check_breakers([1.0], equity_now=49_000, month_start_index=1.0,
                            cfg=self.cfg)
        self.assertTrue(br.triggered)
        self.assertEqual(br.name, "hard_floor")

    def test_no_trigger(self):
        br = check_breakers([1.0, 1.05, 1.02], equity_now=200_000,
                            month_start_index=1.0, cfg=self.cfg)
        self.assertFalse(br.triggered)


if __name__ == "__main__":
    unittest.main()
