import tempfile
import unittest

from helpers import *  # noqa: F401,F403
from smz_trader import ledger
from smz_trader.portfolio import (build_portfolio, compute_twr_index,
                                  equity_jpy, flows_since_last_mark)


def _fill(symbol, side, qty, price, fx, fee=0.0):
    return {"date": "2026-01-05", "symbol": symbol, "side": side, "qty": qty,
            "price": price, "ccy": "USD", "fx": fx, "fee_jpy": fee,
            "notional_jpy": qty * price * fx, "reason": "test"}


class TestPortfolio(unittest.TestCase):
    def test_replay_and_equity(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 200000, "note": ""})
            ledger.append_event(d, ledger.FILL, _fill("SPY", "BUY", 2, 500.0, 150.0, fee=75.0))
            events = ledger.read_events(d)
            pf = build_portfolio(events)
            # 現金 = 200000 - 2*500*150 - 75 = 49925
            self.assertAlmostEqual(pf.cash_jpy, 49925.0)
            self.assertAlmostEqual(pf.position_qty("SPY"), 2.0)
            eq = equity_jpy(pf, {"SPY": 510.0}, 150.0)
            self.assertAlmostEqual(eq, 49925.0 + 2 * 510 * 150)

    def test_sell_and_close(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 200000, "note": ""})
            ledger.append_event(d, ledger.FILL, _fill("SPY", "BUY", 2, 500.0, 150.0))
            ledger.append_event(d, ledger.FILL, _fill("SPY", "SELL", 2, 520.0, 150.0, fee=78.0))
            pf = build_portfolio(ledger.read_events(d))
            self.assertEqual(pf.position_qty("SPY"), 0)
            self.assertNotIn("SPY", pf.positions)
            # 200000 - 150000 + (156000 - 78)
            self.assertAlmostEqual(pf.cash_jpy, 200000 - 150000 + 156000 - 78)

    def test_withdraw_and_flows(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 200000, "note": ""})
            ledger.append_event(d, ledger.MARK, {"date": "2026-01-01", "equity_jpy": 200000,
                                                 "net_flow_jpy": 200000, "twr_index": 1.0,
                                                 "drawdown": 0.0})
            ledger.append_event(d, ledger.WITHDRAW, {"amount_jpy": 50000, "note": ""})
            events = ledger.read_events(d)
            pf = build_portfolio(events)
            self.assertAlmostEqual(pf.cash_jpy, 150000)
            self.assertAlmostEqual(flows_since_last_mark(events), -50000)
            # 出金しただけなら運用成績(TWR)は変わらない
            idx = compute_twr_index(events, equity_now=150000, flows_now=-50000)
            self.assertAlmostEqual(idx, 1.0)

    def test_twr_up(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 100000, "note": ""})
            ledger.append_event(d, ledger.MARK, {"date": "2026-01-01", "equity_jpy": 100000,
                                                 "net_flow_jpy": 100000, "twr_index": 1.0,
                                                 "drawdown": 0.0})
            events = ledger.read_events(d)
            idx = compute_twr_index(events, equity_now=110000, flows_now=0.0)
            self.assertAlmostEqual(idx, 1.1)


if __name__ == "__main__":
    unittest.main()
