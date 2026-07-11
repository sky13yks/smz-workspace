"""市場データ層。

デフォルトは Stooq (https://stooq.com) の無料日足CSV。標準ライブラリのみで動作。
テスト/オフライン用に CSVディレクトリプロバイダを用意。
どのプロバイダも同じ形式の list[Bar] を返す(古い→新しい順)。
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class DataUnavailable(Exception):
    """データ取得不能。フェイルセーフ原則: この例外時は何も売買しない。"""


@dataclass(frozen=True)
class Bar:
    date: str  # ISO形式 YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


def symbol_ccy(symbol: str) -> str:
    """銘柄の建値通貨。日本株(.JP)はJPY、それ以外はUSDとみなす。"""
    return "JPY" if symbol.upper().endswith(".JP") else "USD"


def to_stooq(symbol: str) -> str:
    s = symbol.upper()
    if s == "USDJPY":
        return "usdjpy"
    if s.endswith(".JP"):
        return s.lower()
    return s.lower() + ".us"


def parse_csv_bars(text: str) -> list[Bar]:
    """Stooq形式CSV(Date,Open,High,Low,Close[,Volume])をパース。"""
    bars: list[Bar] = []
    for line in text.strip().splitlines():
        parts = line.strip().split(",")
        if len(parts) < 5 or parts[0].lower() == "date":
            continue
        try:
            d = parts[0]
            o, h, l, c = (float(parts[i]) for i in range(1, 5))
            v = float(parts[5]) if len(parts) > 5 and parts[5] not in ("", "-") else 0.0
        except ValueError:
            continue
        if c <= 0:
            continue
        bars.append(Bar(date=d, open=o, high=h, low=l, close=c, volume=v))
    bars.sort(key=lambda b: b.date)
    return bars


class StooqProvider:
    """Stooqの日足CSVを取得し、ローカルキャッシュする。"""

    BASE = "https://stooq.com/q/d/l/?s={code}&i=d"

    def __init__(self, cache_dir: str | Path, max_age_hours: float = 12.0,
                 offline: bool = False, timeout: float = 30.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age = max_age_hours * 3600
        self.offline = offline
        self.timeout = timeout

    def _cache_file(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol.upper().replace('/', '_')}.csv"

    def history(self, symbol: str) -> list[Bar]:
        cache = self._cache_file(symbol)
        fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < self.max_age
        if fresh or (self.offline and cache.exists()):
            bars = parse_csv_bars(cache.read_text())
            if bars:
                return bars
        if self.offline:
            raise DataUnavailable(f"{symbol}: オフラインでキャッシュなし")
        url = self.BASE.format(code=to_stooq(symbol))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "smz-trader/0.1"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            # ネットワーク断でも古いキャッシュがあれば継続(レポートに注記される)
            if cache.exists():
                bars = parse_csv_bars(cache.read_text())
                if bars:
                    return bars
            raise DataUnavailable(f"{symbol}: 取得失敗 ({e})") from e
        bars = parse_csv_bars(text)
        if not bars:
            if cache.exists():
                old = parse_csv_bars(cache.read_text())
                if old:
                    return old
            raise DataUnavailable(f"{symbol}: データが空(銘柄コード確認: {url})")
        cache.write_text(text)
        return bars


class CsvDirProvider:
    """ディレクトリ内の {SYMBOL}.csv を読むだけのプロバイダ(テスト/オフライン/バックテスト用)。"""

    def __init__(self, csv_dir: str | Path):
        self.csv_dir = Path(csv_dir)

    def history(self, symbol: str) -> list[Bar]:
        f = self.csv_dir / f"{symbol.upper()}.csv"
        if not f.exists():
            raise DataUnavailable(f"{symbol}: {f} がありません")
        bars = parse_csv_bars(f.read_text())
        if not bars:
            raise DataUnavailable(f"{symbol}: {f} が空です")
        return bars


def make_provider(cfg, offline: bool = False):
    """設定に応じたプロバイダを生成。"""
    if cfg.data_provider == "csv":
        if not cfg.csv_dir:
            raise DataUnavailable("data.provider=csv ですが data.csv_dir が未設定です")
        return CsvDirProvider(cfg.csv_dir)
    return StooqProvider(
        cache_dir=cfg.state_dir / "cache",
        max_age_hours=cfg.cache_max_age_hours,
        offline=offline,
    )


def fetch_all(provider, symbols: list[str]) -> dict[str, list[Bar]]:
    """全銘柄の履歴を取得。1銘柄でも失敗したら DataUnavailable(フェイルセーフ)。"""
    out: dict[str, list[Bar]] = {}
    failed: list[str] = []
    for s in symbols:
        try:
            out[s] = provider.history(s)
        except DataUnavailable:
            failed.append(s)
    if failed:
        raise DataUnavailable("取得失敗: " + ", ".join(failed))
    return out
