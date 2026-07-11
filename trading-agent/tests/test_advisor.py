import unittest

from helpers import *  # noqa: F401,F403
from smz_trader.advisor import AdvisorResult, apply_decisions
from smz_trader.risk import Order


class TestAdvisorGuardrails(unittest.TestCase):
    """AIの権限が「リスク低減方向のみ」であることの検証。"""

    def _orders(self):
        return [Order("AAA", "BUY", qty=10, est_price=50.0),
                Order("BBB", "SELL", qty=5, est_price=40.0)]

    def test_veto_removes_buy(self):
        res = AdvisorResult(available=True, decisions=[
            {"symbol": "AAA", "action": "veto", "reason": "test"}])
        out, applied = apply_decisions(self._orders(), res, veto_power=True)
        self.assertEqual([o.symbol for o in out], ["BBB"])
        self.assertEqual(len(applied), 1)

    def test_veto_cannot_block_sell(self):
        res = AdvisorResult(available=True, decisions=[
            {"symbol": "BBB", "action": "veto", "reason": "売らないで"}])
        out, applied = apply_decisions(self._orders(), res, veto_power=True)
        # SELLはそのまま残る(AIはリスク低減を妨害できない)
        self.assertIn("BBB", [o.symbol for o in out])
        self.assertEqual(applied, [])

    def test_downsize_clamped(self):
        res = AdvisorResult(available=True, decisions=[
            {"symbol": "AAA", "action": "downsize", "factor": 5.0, "reason": "増やせ"}])
        out, applied = apply_decisions(self._orders(), res, veto_power=True)
        aaa = next(o for o in out if o.symbol == "AAA")
        # factor>1(増額)はクランプされ、増えることはない
        self.assertLessEqual(aaa.qty, 10 * 0.9 + 1e-9)

    def test_unavailable_passthrough(self):
        res = AdvisorResult(available=False, skip_reason="no key")
        orders = self._orders()
        out, applied = apply_decisions(orders, res, veto_power=True)
        self.assertEqual(out, orders)

    def test_no_veto_power(self):
        res = AdvisorResult(available=True, decisions=[
            {"symbol": "AAA", "action": "veto", "reason": "x"}])
        orders = self._orders()
        out, _ = apply_decisions(orders, res, veto_power=False)
        self.assertEqual(out, orders)


if __name__ == "__main__":
    unittest.main()
