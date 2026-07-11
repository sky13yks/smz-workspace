"""設定ファイル(config.toml)の読み込みと検証。"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    # account
    base_currency: str
    start_cash_jpy: float
    hard_floor_jpy: float
    # mode
    trading: str
    fractional: bool
    # paper
    inception: str
    # strategy
    core_weight: float
    satellite_weight: float
    satellite_top_n: int
    max_weight_per_name: float
    band: float
    mom_lookback_days: int
    mom_skip_days: int
    trend_sma_days: int
    vol_lookback_days: int
    vol_target_annual: float
    min_order_jpy: float
    # risk
    max_drawdown: float
    monthly_loss_limit: float
    cash_buffer: float
    slippage_bps: float
    commission_bps: float
    commission_min_jpy: float
    # universe
    core: list[str]
    trend_ref: str
    fx: str
    satellite: list[str]
    # data
    data_provider: str
    cache_max_age_hours: float
    csv_dir: str
    # ai
    ai_enabled: bool
    ai_veto_power: bool
    ai_model: str
    ai_max_tokens: int
    # 場所
    config_path: Path = field(default_factory=Path)

    @property
    def all_symbols(self) -> list[str]:
        """価格データが必要な全銘柄(FX込み)。"""
        return list(dict.fromkeys(self.core + self.satellite + [self.fx]))

    @property
    def tradable_symbols(self) -> set[str]:
        """発注が許可される銘柄(ホワイトリスト)。"""
        return set(self.core) | set(self.satellite)

    @property
    def state_dir(self) -> Path:
        return self.config_path.parent.parent / "state"


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    acct = raw.get("account", {})
    mode = raw.get("mode", {})
    paper = raw.get("paper", {})
    strat = raw.get("strategy", {})
    risk = raw.get("risk", {})
    uni = raw.get("universe", {})
    data = raw.get("data", {})
    ai = raw.get("ai", {})

    cfg = Config(
        base_currency=acct.get("base_currency", "JPY"),
        start_cash_jpy=float(acct.get("start_cash_jpy", 200_000)),
        hard_floor_jpy=float(acct.get("hard_floor_jpy", 50_000)),
        trading=mode.get("trading", "paper"),
        fractional=bool(mode.get("fractional", True)),
        inception=paper.get("inception", "2026-07-14"),
        core_weight=float(strat.get("core_weight", 0.70)),
        satellite_weight=float(strat.get("satellite_weight", 0.30)),
        satellite_top_n=int(strat.get("satellite_top_n", 5)),
        max_weight_per_name=float(strat.get("max_weight_per_name", 0.10)),
        band=float(strat.get("band", 0.20)),
        mom_lookback_days=int(strat.get("mom_lookback_days", 252)),
        mom_skip_days=int(strat.get("mom_skip_days", 21)),
        trend_sma_days=int(strat.get("trend_sma_days", 200)),
        vol_lookback_days=int(strat.get("vol_lookback_days", 60)),
        vol_target_annual=float(strat.get("vol_target_annual", 0.25)),
        min_order_jpy=float(strat.get("min_order_jpy", 1000)),
        max_drawdown=float(risk.get("max_drawdown", 0.25)),
        monthly_loss_limit=float(risk.get("monthly_loss_limit", 0.10)),
        cash_buffer=float(risk.get("cash_buffer", 0.01)),
        slippage_bps=float(risk.get("slippage_bps", 10)),
        commission_bps=float(risk.get("commission_bps", 5)),
        commission_min_jpy=float(risk.get("commission_min_jpy", 0)),
        core=list(uni.get("core", ["SPY", "QQQ"])),
        trend_ref=uni.get("trend_ref", "SPY"),
        fx=uni.get("fx", "USDJPY"),
        satellite=list(uni.get("satellite", [])),
        data_provider=data.get("provider", "stooq"),
        cache_max_age_hours=float(data.get("cache_max_age_hours", 12)),
        csv_dir=data.get("csv_dir", ""),
        ai_enabled=bool(ai.get("enabled", True)),
        ai_veto_power=bool(ai.get("veto_power", True)),
        ai_model=ai.get("model", "claude-opus-4-8"),
        ai_max_tokens=int(ai.get("max_tokens", 2048)),
        config_path=path,
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    errors = []
    if cfg.trading not in ("paper", "live"):
        errors.append(f"mode.trading が不正: {cfg.trading}")
    if cfg.core_weight + cfg.satellite_weight > 1.0 + 1e-9:
        errors.append("core_weight + satellite_weight が 1.0 を超えています")
    if not (0 < cfg.max_drawdown < 1):
        errors.append("risk.max_drawdown は 0〜1 の範囲")
    if cfg.trend_ref not in cfg.core and cfg.trend_ref not in cfg.satellite:
        # trend_ref は core に含めるのが通常だが、価格取得対象なら許容
        pass
    if cfg.hard_floor_jpy < 0:
        errors.append("hard_floor_jpy は 0 以上")
    if errors:
        raise ValueError("設定エラー: " + "; ".join(errors))
