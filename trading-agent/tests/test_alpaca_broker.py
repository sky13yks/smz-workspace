"""AlpacaBroker のユニットテスト。

実ネットワークには接続せず、Alpaca REST を模した FakeHttp を注入して
発注→ポーリング→約定/未約定、冪等性、ライブ多重ゲート、照合を検証する。
"""

import unittest

from helpers import make_test_config, write_universe
import tempfile

from smz_trader.broker import (AlpacaBroker, BrokerError, LIVE_CONFIRM_PHRASE,
                               PaperBroker, make_broker, require_live_confirmation)
from smz_trader.risk import Order


class FakeHttp:
    """Alpaca REST v2 の最小シミュレータ。

    submit した注文は fill_plan に従って状態遷移する:
      fill_plan[symbol] = "filled" | "rejected" | "pending"
    "pending" はポーリングしても filled にならない(市場閉場を模す)。
    """

    def __init__(self, base_url="https://paper-api.alpaca.markets",
                 fill_plan=None, account=None, positions=None):
        self.base_url = base_url.rstrip("/")
        self.fill_plan = fill_plan or {}
        self._account = account or {
            "status": "ACTIVE", "currency": "USD", "cash": "10000",
            "buying_power": "10000"}
        self._positions = positions or []
        self.orders_by_id = {}
        self.orders_by_coid = {}
        self.submit_count = 0
        self._seq = 0

    def request(self, method, path, body=None):
        if path == "/v2/account":
            return 200, self._account
        if path == "/v2/positions":
            return 200, self._positions
        if method == "POST" and path == "/v2/orders":
            return self._submit(body)
        if path.startswith("/v2/orders:by_client_order_id"):
            coid = path.split("client_order_id=")[1]
            od = self.orders_by_coid.get(coid)
            return (200, od) if od else (404, {"message": "not found"})
        if path.startswith("/v2/orders/"):
            oid = path.rsplit("/", 1)[1]
            od = self.orders_by_id.get(oid)
            return (200, od) if od else (404, {"message": "not found"})
        if path.startswith("/v2/orders?"):
            return 200, list(self.orders_by_id.values())
        return 404, {"message": f"unhandled {method} {path}"}

    def _submit(self, body):
        coid = body["client_order_id"]
        if coid in self.orders_by_coid:  # 冪等: 重複IDは拒否
            return 422, {"message": "client_order_id must be unique"}
        self.submit_count += 1
        self._seq += 1
        oid = f"oid-{self._seq}"
        sym = body["symbol"]
        plan = self.fill_plan.get(sym, "filled")
        qty = body["qty"]
        if plan == "rejected":
            od = {"id": oid, "client_order_id": coid, "symbol": sym,
                  "side": body["side"], "status": "rejected", "filled_qty": "0"}
        elif plan == "pending":
            od = {"id": oid, "client_order_id": coid, "symbol": sym,
                  "side": body["side"], "status": "accepted", "filled_qty": "0"}
        else:  # filled
            od = {"id": oid, "client_order_id": coid, "symbol": sym,
                  "side": body["side"], "status": "filled", "filled_qty": qty,
                  "filled_avg_price": "100.0", "filled_at": "2026-08-03T13:31:00Z"}
        self.orders_by_id[oid] = od
        self.orders_by_coid[coid] = od
        return 200, od


def _live_cfg(tmp):
    csv = tmp + "/csv"
    write_universe(csv, {"SPY": (100, 0.0), "QQQ": (100, 0.0), "AAA": (50, 0.0),
                         "BBB": (50, 0.0), "CCC": (50, 0.0), "USDJPY": (150, 0.0)})
    return make_test_config(tmp, csv)


class TestAlpacaExecute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = _live_cfg(self.tmp.name)

    def _broker(self, **kw):
        http = FakeHttp(**kw)
        return AlpacaBroker(self.cfg, http=http, sleep=lambda s: None,
                            order_timeout_s=0, poll_interval_s=0), http

    def test_buy_fills(self):
        broker, http = self._broker()
        fills, rejects = broker.execute(
            [Order("SPY", "BUY", qty=2, est_price=100.0)],
            {"SPY": 100.0}, fx=150.0, cash_jpy=100_000, date="2026-08-03")
        self.assertEqual(len(fills), 1)
        self.assertEqual(len(rejects), 0)
        f = fills[0]
        self.assertEqual(f.symbol, "SPY")
        self.assertEqual(f.qty, 2.0)
        self.assertAlmostEqual(f.price, 100.0)
        # notional = 2 * 100 * 150 = 30000円
        self.assertAlmostEqual(f.notional_jpy, 30000.0, places=1)
        self.assertTrue(f.client_order_id.startswith("smz-2026-08-03-BUY-SPY"))

    def test_rejected_order(self):
        broker, _ = self._broker(fill_plan={"SPY": "rejected"})
        fills, rejects = broker.execute(
            [Order("SPY", "BUY", qty=2, est_price=100.0)],
            {"SPY": 100.0}, fx=150.0, cash_jpy=100_000, date="2026-08-03")
        self.assertEqual(len(fills), 0)
        self.assertEqual(len(rejects), 1)
        self.assertIn("rejected", rejects[0][1])

    def test_pending_when_market_closed(self):
        broker, _ = self._broker(fill_plan={"SPY": "pending"})
        fills, rejects = broker.execute(
            [Order("SPY", "BUY", qty=2, est_price=100.0)],
            {"SPY": 100.0}, fx=150.0, cash_jpy=100_000, date="2026-08-03")
        self.assertEqual(len(fills), 0)
        self.assertEqual(len(rejects), 1)
        self.assertIn("sync-fills", rejects[0][1])

    def test_idempotent_resubmit(self):
        """同じ注文を2回 execute しても二重約定しない(冪等キー)。"""
        http = FakeHttp()
        b1 = AlpacaBroker(self.cfg, http=http, sleep=lambda s: None,
                          order_timeout_s=0, poll_interval_s=0)
        order = [Order("SPY", "BUY", qty=2, est_price=100.0)]
        f1, _ = b1.execute(order, {"SPY": 100.0}, 150.0, 100_000, "2026-08-03")
        f2, _ = b1.execute(order, {"SPY": 100.0}, 150.0, 100_000, "2026-08-03")
        self.assertEqual(len(f1), 1)
        self.assertEqual(len(f2), 1)
        self.assertEqual(http.submit_count, 1)  # 実送信は1回だけ
        self.assertEqual(f1[0].client_order_id, f2[0].client_order_id)

    def test_non_usd_rejected(self):
        broker, _ = self._broker()
        fills, rejects = broker.execute(
            [Order("7203.JP", "BUY", qty=1, est_price=1000.0)],
            {"7203.JP": 1000.0}, fx=150.0, cash_jpy=100_000, date="2026-08-03")
        self.assertEqual(len(fills), 0)
        self.assertIn("USD", rejects[0][1])

    def test_sell_before_buy_ordering(self):
        broker, http = self._broker()
        orders = [Order("SPY", "BUY", qty=1, est_price=100.0),
                  Order("QQQ", "SELL", qty=1, est_price=100.0)]
        broker.execute(orders, {"SPY": 100.0, "QQQ": 100.0}, 150.0, 100_000, "2026-08-03")
        # SELL が先に送信される
        first = min(http.orders_by_id.values(), key=lambda o: o["id"])
        self.assertEqual(first["side"], "sell")


class TestLiveGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_paper_config_returns_paper(self):
        cfg = _live_cfg(self.tmp.name)  # paper
        self.assertIsInstance(make_broker(cfg), PaperBroker)

    def test_live_without_confirmation_blocked(self):
        with self.assertRaises(BrokerError):
            require_live_confirmation(env={})

    def test_live_with_wrong_phrase_blocked(self):
        with self.assertRaises(BrokerError):
            require_live_confirmation(env={"SMZ_LIVE_CONFIRM": "yes"})

    def test_live_with_correct_phrase_ok(self):
        require_live_confirmation(env={"SMZ_LIVE_CONFIRM": LIVE_CONFIRM_PHRASE})


class TestReconcile(unittest.TestCase):
    def test_reconcile_read_only(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cfg = _live_cfg(tmp.name)
        http = FakeHttp(positions=[{"symbol": "SPY", "qty": "2"}])
        broker = AlpacaBroker(cfg, http=http)
        pos = broker.positions()
        self.assertEqual(pos[0]["symbol"], "SPY")
        acct = broker.account()
        self.assertEqual(acct["status"], "ACTIVE")


if __name__ == "__main__":
    unittest.main()
