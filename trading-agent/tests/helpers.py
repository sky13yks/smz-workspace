"""テスト用ヘルパー: 決定論的な合成価格データ生成。"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def make_csv(path, start_price: float, daily_drift: float, n: int,
             start_date: str = "2024-01-01", wiggle: float = 0.004):
    """幾何ドリフト+決定論的な揺らぎの日足CSVを書き出す(土日スキップ)。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    d = dt.date.fromisoformat(start_date)
    px = start_price
    lines = ["Date,Open,High,Low,Close,Volume"]
    i = 0
    while i < n:
        if d.weekday() < 5:
            w = wiggle if i % 2 == 0 else -wiggle
            close = px * (1 + w)
            lines.append(f"{d.isoformat()},{px:.4f},{close * 1.002:.4f},"
                         f"{px * 0.998:.4f},{close:.4f},1000000")
            px = px * (1 + daily_drift)
            i += 1
        d += dt.timedelta(days=1)
    Path(path).write_text("\n".join(lines))


def write_universe(tmpdir, spec: dict[str, tuple[float, float]], n: int = 320,
                   start_date: str = "2024-01-01"):
    """spec: {SYMBOL: (start_price, daily_drift)} を一括生成。"""
    for sym, (p0, drift) in spec.items():
        make_csv(Path(tmpdir) / f"{sym}.csv", p0, drift, n, start_date)


def make_test_config(tmpdir, csv_dir, satellite=("AAA", "BBB", "CCC"),
                     core=("SPY", "QQQ"), ai_enabled=False, **overrides) -> "object":
    """CSVプロバイダを使うテスト用Configを生成する。"""
    from smz_trader.config import load_config
    sat = ", ".join(f'"{s}"' for s in satellite)
    cor = ", ".join(f'"{s}"' for s in core)
    extra_risk = overrides.get("risk", "")
    extra_strategy = overrides.get("strategy", "")
    text = f"""
[account]
start_cash_jpy = 200000
hard_floor_jpy = {overrides.get('hard_floor_jpy', 50000)}

[mode]
trading = "paper"
fractional = true

[paper]
inception = "{start_or('2024-01-01', overrides)}"

[strategy]
core_weight = 0.70
satellite_weight = 0.30
satellite_top_n = 2
max_weight_per_name = 0.20
band = 0.20
mom_lookback_days = 200
mom_skip_days = 10
trend_sma_days = 150
vol_lookback_days = 60
vol_target_annual = 0.25
min_order_jpy = 500
{extra_strategy}

[risk]
max_drawdown = {overrides.get('max_drawdown', 0.25)}
monthly_loss_limit = {overrides.get('monthly_loss_limit', 0.10)}
cash_buffer = 0.01
slippage_bps = 10
commission_bps = 5
commission_min_jpy = 0
{extra_risk}

[universe]
core = [{cor}]
trend_ref = "SPY"
fx = "USDJPY"
satellite = [{sat}]

[data]
provider = "csv"
cache_max_age_hours = 12
csv_dir = "{csv_dir}"

[ai]
enabled = {"true" if ai_enabled else "false"}
veto_power = true
model = "claude-opus-4-8"
max_tokens = 2048
"""
    cfg_dir = Path(tmpdir) / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    p = cfg_dir / "config.toml"
    p.write_text(text)
    return load_config(p)


def start_or(default, overrides):
    return overrides.get("inception", default)
