"""AIアドバイザー層(Claude API)。

役割は「リスクレビュー担当者」: ルールベース戦略が出した注文を点検し、
懸念があれば 買い注文の拒否(veto)または縮小(downsize)だけができる。
新規銘柄の追加・数量の増額・リスク設定の変更は構造的に不可能。
利用不能時(キー未設定/ネットワーク断/SDK未導入)はスキップされ、
システムはルールベースのみで完結する(フェイルセーフ)。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .risk import Order

SYSTEM_PROMPT = """あなたは個人のシステマティック株式運用口座のリスクレビュー担当者です。
ルールベース戦略(トレンドフィルタ付きモメンタム、コア・サテライト)が生成した
リバランス注文を最終点検してください。

あなたにできることは以下だけです:
- approve: 注文を承認
- veto: 買い注文を取り消す(明確なリスク根拠がある場合のみ)
- downsize: 買い注文を縮小する(factor: 0.1〜0.9)

できないこと(提案しても無視されます):
- 新しい銘柄の追加、数量の増額、売り注文の妨害、リスク設定の変更

判断基準: 明白な構造的リスク(極端なボラティリティ、データ異常の兆候、
ポートフォリオの過度な集中)のみ。市場予測に基づく veto は避け、
迷ったら approve してください。戦略の規律を尊重します。

memo には日本語で簡潔なレビュー所感を書いてください(運用者が毎日読みます)。"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "action": {"type": "string", "enum": ["approve", "veto", "downsize"]},
                    "factor": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["symbol", "action", "reason"],
                "additionalProperties": False,
            },
        },
        "memo": {"type": "string"},
    },
    "required": ["decisions", "memo"],
    "additionalProperties": False,
}


@dataclass
class AdvisorResult:
    available: bool
    memo: str = ""
    decisions: list[dict] = field(default_factory=list)
    model: str = ""
    prompt_sha256: str = ""
    skip_reason: str = ""


def review(context: dict, cfg) -> AdvisorResult:
    """注文コンテキストをClaudeに渡してレビュー結果を得る。失敗時は available=False。"""
    if not cfg.ai_enabled:
        return AdvisorResult(available=False, skip_reason="ai.enabled=false")
    try:
        import anthropic  # 遅延import(コア機能は依存しない)
    except ImportError:
        return AdvisorResult(available=False,
                             skip_reason="anthropicパッケージ未導入(pip install 'smz-trader[ai]')")
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return AdvisorResult(available=False, skip_reason="ANTHROPIC_API_KEY未設定")

    user_content = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    prompt_sha = hashlib.sha256((SYSTEM_PROMPT + user_content).encode()).hexdigest()
    try:
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=cfg.ai_model,
            max_tokens=cfg.ai_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        )
        if resp.stop_reason == "refusal":
            return AdvisorResult(available=False, skip_reason="モデルが応答を拒否")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        data = json.loads(text)
        return AdvisorResult(available=True, memo=data.get("memo", ""),
                             decisions=data.get("decisions", []),
                             model=cfg.ai_model, prompt_sha256=prompt_sha)
    except Exception as e:  # ネットワーク・API・パース失敗は全てスキップ扱い
        return AdvisorResult(available=False, skip_reason=f"APIエラー: {e}")


def apply_decisions(orders: list[Order], result: AdvisorResult,
                    veto_power: bool) -> tuple[list[Order], list[str]]:
    """AI判断を注文に適用する。リスク低減方向のみ有効。

    - veto/downsize は BUY 注文にのみ作用(SELLを止めることはできない)
    - downsize の factor は 0.1〜0.9 にクランプ
    """
    if not result.available or not veto_power:
        return orders, []
    actions = {d["symbol"]: d for d in result.decisions if isinstance(d, dict)}
    out: list[Order] = []
    applied: list[str] = []
    for o in orders:
        d = actions.get(o.symbol)
        if d is None or o.side != "BUY":
            out.append(o)
            continue
        act = d.get("action")
        if act == "veto":
            applied.append(f"{o.symbol}: AI veto ({d.get('reason', '')})")
            continue
        if act == "downsize":
            factor = min(max(float(d.get("factor", 0.5)), 0.1), 0.9)
            out.append(Order(symbol=o.symbol, side=o.side, qty=round(o.qty * factor, 4),
                             est_price=o.est_price, reason=o.reason + f" [AI downsize x{factor}]"))
            applied.append(f"{o.symbol}: AI downsize x{factor} ({d.get('reason', '')})")
            continue
        out.append(o)
    return out, applied


def build_context(date: str, equity: float, drawdown: float, pf_weights: dict,
                  orders: list[Order], strategy_info: dict, fx: float) -> dict:
    return {
        "date": date,
        "portfolio": {
            "equity_jpy": round(equity),
            "drawdown_from_peak": round(drawdown, 4),
            "current_weights": {k: round(v, 4) for k, v in pf_weights.items()},
            "usdjpy": fx,
        },
        "proposed_orders": [
            {"symbol": o.symbol, "side": o.side, "qty": o.qty,
             "est_price": o.est_price, "reason": o.reason}
            for o in orders
        ],
        "strategy_info": strategy_info,
    }
