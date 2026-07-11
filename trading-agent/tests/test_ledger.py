import json
import tempfile
import unittest
from pathlib import Path

from helpers import *  # noqa: F401,F403
from smz_trader import ledger


class TestLedger(unittest.TestCase):
    def test_append_read_verify(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 200000, "note": "初回"})
            ledger.append_event(d, ledger.MARK, {"date": "2026-01-01", "equity_jpy": 200000,
                                                 "net_flow_jpy": 0, "twr_index": 1.0,
                                                 "drawdown": 0.0})
            events = ledger.read_events(d)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["type"], ledger.DEPOSIT)
            ok, msg = ledger.verify_chain(events)
            self.assertTrue(ok, msg)

    def test_tamper_detection(self):
        with tempfile.TemporaryDirectory() as d:
            ledger.append_event(d, ledger.DEPOSIT, {"amount_jpy": 200000, "note": ""})
            ledger.append_event(d, ledger.WITHDRAW, {"amount_jpy": 1000, "note": ""})
            p = ledger.ledger_path(d)
            lines = p.read_text().splitlines()
            e = json.loads(lines[0])
            e["data"]["amount_jpy"] = 999999  # 改竄
            lines[0] = json.dumps(e, ensure_ascii=False, sort_keys=True)
            p.write_text("\n".join(lines) + "\n")
            ok, msg = ledger.verify_chain(ledger.read_events(d))
            self.assertFalse(ok)
            self.assertIn("hash", msg)

    def test_deletion_detection(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(3):
                ledger.append_event(d, ledger.NOTE, {"text": f"n{i}"})
            p = ledger.ledger_path(d)
            lines = p.read_text().splitlines()
            p.write_text("\n".join([lines[0], lines[2]]) + "\n")  # 途中を削除
            ok, _ = ledger.verify_chain(ledger.read_events(d))
            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
