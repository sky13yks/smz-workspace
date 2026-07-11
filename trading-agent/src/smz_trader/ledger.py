"""追記専用・ハッシュ連鎖付きの取引台帳(JSONL)。

全ての資金移動・売買・停止/再開・AI判断を記録する。各イベントは直前イベントの
ハッシュを含むため、後からの改竄・欠落を verify_chain() で検出できる。
税務(譲渡損益計算)と監査の一次資料。
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

LEDGER_NAME = "ledger.jsonl"

# イベント種別
DEPOSIT = "DEPOSIT"        # 入金 {amount_jpy, note}
WITHDRAW = "WITHDRAW"      # 出金 {amount_jpy, note}
FILL = "FILL"              # 約定 {date, symbol, side, qty, price, ccy, fx, fee_jpy, notional_jpy, reason}
MARK = "MARK"              # 日次評価 {date, equity_jpy, net_flow_jpy, twr_index, drawdown}
HALT = "HALT"              # 停止 {reason, breaker}
RESUME = "RESUME"          # 再開 {note}
NOTE = "NOTE"              # メモ/異常 {text}
AI_MEMO = "AI_MEMO"        # AIアドバイザー判断 {model, memo, decisions, prompt_sha256}


def ledger_path(state_dir: str | Path) -> Path:
    return Path(state_dir) / LEDGER_NAME


def _hash_event(prev_hash: str, core: dict) -> str:
    payload = prev_hash + json.dumps(core, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_events(state_dir: str | Path) -> list[dict]:
    p = ledger_path(state_dir)
    if not p.exists():
        return []
    events = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


def append_event(state_dir: str | Path, etype: str, data: dict,
                 ts: str | None = None) -> dict:
    p = ledger_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    events = read_events(state_dir)
    prev_hash = events[-1]["hash"] if events else "GENESIS"
    core = {
        "seq": len(events) + 1,
        "ts": ts or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "type": etype,
        "data": data,
    }
    event = dict(core)
    event["prev_hash"] = prev_hash
    event["hash"] = _hash_event(prev_hash, core)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def verify_chain(events: list[dict]) -> tuple[bool, str]:
    prev_hash = "GENESIS"
    for i, e in enumerate(events):
        core = {"seq": e.get("seq"), "ts": e.get("ts"),
                "type": e.get("type"), "data": e.get("data")}
        if e.get("prev_hash") != prev_hash:
            return False, f"イベント{i + 1}: prev_hash 不一致(改竄または欠落の疑い)"
        if e.get("hash") != _hash_event(prev_hash, core):
            return False, f"イベント{i + 1}: hash 不一致(内容が改変されています)"
        if e.get("seq") != i + 1:
            return False, f"イベント{i + 1}: seq 不一致"
        prev_hash = e["hash"]
    return True, f"OK ({len(events)}イベント)"
