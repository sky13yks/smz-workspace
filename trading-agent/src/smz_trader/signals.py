"""テクニカル指標(純関数のみ、副作用なし)。"""

from __future__ import annotations

import math


def sma(values: list[float], n: int) -> float | None:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


def momentum(closes: list[float], lookback: int = 252, skip: int = 21) -> float | None:
    """12-1モメンタム: 直近skip日を除いたlookback日リターン。"""
    if len(closes) < lookback + 1:
        return None
    end = closes[-1 - skip] if skip > 0 else closes[-1]
    start = closes[-1 - lookback]
    if start <= 0:
        return None
    return end / start - 1.0


def total_return(closes: list[float], n: int) -> float | None:
    if len(closes) < n + 1 or closes[-1 - n] <= 0:
        return None
    return closes[-1] / closes[-1 - n] - 1.0


def realized_vol_annual(closes: list[float], n: int = 60) -> float | None:
    """直近n日の日次対数リターンの標準偏差を年率換算。"""
    if len(closes) < n + 1:
        return None
    rets = []
    window = closes[-(n + 1):]
    for i in range(1, len(window)):
        if window[i - 1] > 0 and window[i] > 0:
            rets.append(math.log(window[i] / window[i - 1]))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252)


def max_drawdown(series: list[float]) -> float:
    """系列の最大ドローダウン(0.25 = -25%)。"""
    peak = -math.inf
    mdd = 0.0
    for v in series:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, 1.0 - v / peak)
    return mdd


def drawdown_from_peak(series: list[float]) -> float:
    """現在値の高値からのドローダウン。"""
    if not series:
        return 0.0
    peak = max(series)
    if peak <= 0:
        return 0.0
    return max(0.0, 1.0 - series[-1] / peak)
