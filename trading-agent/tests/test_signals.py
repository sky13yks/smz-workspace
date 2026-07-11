import unittest

from helpers import *  # noqa: F401,F403  (sys.path設定)
from smz_trader.signals import (drawdown_from_peak, max_drawdown, momentum,
                                realized_vol_annual, sma)


class TestSignals(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(sma([1, 2], 3))

    def test_momentum_up(self):
        closes = [100 * (1.001 ** i) for i in range(300)]
        m = momentum(closes, lookback=252, skip=21)
        self.assertIsNotNone(m)
        self.assertGreater(m, 0)

    def test_momentum_down(self):
        closes = [100 * (0.999 ** i) for i in range(300)]
        self.assertLess(momentum(closes, 252, 21), 0)

    def test_momentum_insufficient(self):
        self.assertIsNone(momentum([100] * 100, 252, 21))

    def test_vol_positive(self):
        closes = [100 + (1 if i % 2 == 0 else -1) for i in range(100)]
        v = realized_vol_annual(closes, 60)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0)

    def test_max_drawdown(self):
        self.assertAlmostEqual(max_drawdown([100, 80, 90]), 0.2)
        self.assertAlmostEqual(max_drawdown([1, 2, 3]), 0.0)

    def test_drawdown_from_peak(self):
        self.assertAlmostEqual(drawdown_from_peak([1.0, 1.5, 1.2]), 0.2)
        self.assertEqual(drawdown_from_peak([]), 0.0)


if __name__ == "__main__":
    unittest.main()
