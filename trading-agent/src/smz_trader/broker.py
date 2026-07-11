"""ブローカー層。

- PaperBroker: 終値+スリッページで約定させる仮想ブローカー(ペーパー/バックテスト共用)。
- AlpacaBroker: 米国株の実弾ブローカー(Phase 2)。Alpaca REST API v2 を標準ライブラリのみで叩く。
  paper-api.alpaca.markets を使えば「実APIコード経路・偽金」で安全に並走テストできる。
- KabuStationBroker: 日本株の実弾ブローカー(Phase 3、未実装)。

全ブローカーは共通インターフェース:
    execute(orders, prices, fx, cash_jpy, date) -> (fills, rejects)
を持つ。実ブローカーは追加で account()/positions()/recent_orders() を提供する。

ライブ起動は多重ゲート(docs/02 R8):
  1. config の mode.trading="live"
  2. mode.live_broker で実装済みアダプタを指定
  3. 認証情報が環境変数に存在(secrets.env)
  4. 環境変数 SMZ_LIVE_CONFIRM が確認フレーズと完全一致
のすべてを満たさない限り、実弾ブローカーは生成されない。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .data import symbol_ccy
from .risk import Order

# ライブ発注を実際に有効化するための確認フレーズ(環境変数 SMZ_LIVE_CONFIRM に設定)。
# config を live に切り替えただけでは発注できない二重の安全装置。
LIVE_CONFIRM_PHRASE = "I understand this trades real money"


class BrokerError(Exception):
    """ブローカー接続・設定・発注の失敗。フェイルセーフ原則: この例外時は何も売買しない。"""


@dataclass(frozen=True)
class Fill:
    date: str
    symbol: str
    side: str
    qty: float
    price: float      # 現地通貨建て約定価格(スリッページ込み)
    ccy: str
    fx: float         # 約定時のUSDJPY(JPY建ては1.0)
    fee_jpy: float
    notional_jpy: float
    reason: str = ""
    client_order_id: str = ""   # 実ブローカーの冪等キー(ペーパーは空)
    broker_order_id: str = ""   # 実ブローカーの注文ID(照合・追跡用)


class PaperBroker:
    """仮想約定エンジン。現金残高を超える買いは拒否(guardrailの二重チェック)。"""

    def __init__(self, cfg):
        self.cfg = cfg

    def execute(self, orders: list[Order], prices: dict[str, float], fx: float,
                cash_jpy: float, date: str) -> tuple[list[Fill], list[tuple[Order, str]]]:
        fills: list[Fill] = []
        rejects: list[tuple[Order, str]] = []
        cash = cash_jpy
        slip = self.cfg.slippage_bps / 10_000.0
        for o in sorted(orders, key=lambda x: 0 if x.side == "SELL" else 1):
            base_px = prices.get(o.symbol)
            if base_px is None or base_px <= 0:
                rejects.append((o, "価格なし"))
                continue
            px = base_px * (1 + slip) if o.side == "BUY" else base_px * (1 - slip)
            ccy = symbol_ccy(o.symbol)
            rate = fx if ccy == "USD" else 1.0
            notional = o.qty * px * rate
            fee = max(self.cfg.commission_min_jpy,
                      notional * self.cfg.commission_bps / 10_000.0)
            if o.side == "BUY":
                if notional + fee > cash + 1e-6:
                    rejects.append((o, f"現金不足({cash:,.0f}円 < {notional + fee:,.0f}円)"))
                    continue
                cash -= notional + fee
            else:
                cash += notional - fee
            fills.append(Fill(date=date, symbol=o.symbol, side=o.side, qty=o.qty,
                              price=round(px, 6), ccy=ccy, fx=rate, fee_jpy=round(fee, 2),
                              notional_jpy=round(notional, 2), reason=o.reason))
        return fills, rejects


# =====================================================================
# 実ブローカー: HTTP 層(標準ライブラリのみ・テスト注入可能)
# =====================================================================

class HttpJson:
    """urllib ベースの最小 JSON HTTP クライアント。テストでは差し替え可能。"""

    def __init__(self, base_url: str, headers: dict[str, str], timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.headers = headers
        self.timeout = timeout

    def request(self, method: str, path: str,
                body: dict | None = None) -> tuple[int, dict]:
        url = self.base_url + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        for k, v in self.headers.items():
            req.add_header(k, v)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return resp.status, (json.loads(text) if text.strip() else {})
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(text) if text.strip() else {}
            except json.JSONDecodeError:
                payload = {"message": text}
            return e.code, payload
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise BrokerError(f"ブローカー通信失敗: {e}") from e


# 約定完了とみなす端末状態 / 失敗端末状態
_FILLED = "filled"
_TERMINAL_FAIL = {"canceled", "rejected", "expired", "done_for_day", "suspended", "stopped"}


class AlpacaBroker:
    """Alpaca 米国株ブローカー(現物・端数株)。

    - 認証は環境変数 ALPACA_API_KEY / ALPACA_SECRET_KEY / ALPACA_BASE_URL。
    - ベースURLが paper-api.* なら偽金の並走テスト、api.* なら実弾。
    - 冪等性: 各注文に決定論的な client_order_id を付与。再実行しても二重約定しない
      (同一IDは Alpaca 側で拒否 → 既存注文を照会してポーリング)。
    - 約定完了(filled)のみを Fill として返す。未約定(市場閉場・タイムアウト)は reject
      として返し、注文は working のまま残して後刻 sync-fills で反映する。
    """

    def __init__(self, cfg, http: HttpJson | None = None,
                 sleep=time.sleep, order_timeout_s: float | None = None,
                 poll_interval_s: float = 2.0):
        self.cfg = cfg
        self._sleep = sleep
        self.poll_interval_s = poll_interval_s
        self.order_timeout_s = (
            order_timeout_s if order_timeout_s is not None
            else float(os.environ.get("SMZ_ORDER_TIMEOUT", "90")))
        if http is not None:
            self.http = http
            self.base_url = http.base_url
        else:
            key = os.environ.get("ALPACA_API_KEY", "")
            secret = os.environ.get("ALPACA_SECRET_KEY", "")
            base = os.environ.get("ALPACA_BASE_URL",
                                  "https://paper-api.alpaca.markets")
            if not key or not secret:
                raise BrokerError(
                    "ALPACA_API_KEY / ALPACA_SECRET_KEY が未設定です。"
                    "config/secrets.env に設定して `set -a; source config/secrets.env; set +a`")
            self.http = HttpJson(base, {
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
            })
            self.base_url = base.rstrip("/")

    @property
    def is_paper(self) -> bool:
        return "paper-api" in self.base_url

    # --- 読み取り(照合・プリフライト用) -------------------------------

    def account(self) -> dict:
        status, data = self.http.request("GET", "/v2/account")
        if status != 200:
            raise BrokerError(f"account 取得失敗 ({status}): {data.get('message', data)}")
        return data

    def positions(self) -> list[dict]:
        status, data = self.http.request("GET", "/v2/positions")
        if status != 200:
            raise BrokerError(f"positions 取得失敗 ({status}): {data.get('message', data)}")
        return data if isinstance(data, list) else []

    def recent_orders(self, status_filter: str = "closed",
                      limit: int = 200) -> list[dict]:
        path = f"/v2/orders?status={status_filter}&limit={limit}&direction=desc"
        code, data = self.http.request("GET", path)
        if code != 200:
            raise BrokerError(f"orders 取得失敗 ({code}): {data}")
        return data if isinstance(data, list) else []

    # --- 発注 -----------------------------------------------------------

    def _client_order_id(self, o: Order, date: str) -> str:
        """(日付,銘柄,売買,数量,理由) から決定論的な冪等キーを作る。"""
        h = hashlib.sha256(
            f"{date}|{o.symbol}|{o.side}|{o.qty}|{o.reason}".encode()
        ).hexdigest()[:12]
        return f"smz-{date}-{o.side}-{o.symbol}-{h}"

    def _get_by_coid(self, coid: str) -> dict | None:
        code, data = self.http.request(
            "GET", f"/v2/orders:by_client_order_id?client_order_id={coid}")
        if code == 200 and isinstance(data, dict) and data.get("id"):
            return data
        return None

    def _submit(self, o: Order, coid: str) -> dict:
        """注文を送信。重複IDなら既存注文を返す(冪等)。"""
        body = {
            "symbol": o.symbol,
            "qty": str(o.qty),
            "side": o.side.lower(),
            "type": "market",
            "time_in_force": "day",   # 端数株は market+day のみ許可
            "client_order_id": coid,
        }
        code, data = self.http.request("POST", "/v2/orders", body)
        if code in (200, 201):
            return data
        # 重複 client_order_id → 既に送信済み。既存を照会して継続。
        msg = str(data.get("message", data)).lower()
        if code in (403, 422) and ("client_order_id" in msg or "unique" in msg):
            existing = self._get_by_coid(coid)
            if existing:
                return existing
        raise BrokerError(f"{o.side} {o.symbol} 発注失敗 ({code}): {data.get('message', data)}")

    def _poll(self, order_id: str) -> dict:
        """端末状態(約定/失敗)またはタイムアウトまでポーリング。"""
        deadline = self.order_timeout_s
        elapsed = 0.0
        last = {}
        while True:
            code, data = self.http.request("GET", f"/v2/orders/{order_id}")
            if code == 200 and isinstance(data, dict):
                last = data
                st = data.get("status")
                if st == _FILLED or st in _TERMINAL_FAIL:
                    return data
            if elapsed >= deadline:
                return last or {"status": "timeout"}
            self._sleep(self.poll_interval_s)
            elapsed += self.poll_interval_s

    def _fill_from_order(self, od: dict, o: Order | None, fx: float,
                         date: str) -> Fill:
        sym = od.get("symbol", o.symbol if o else "")
        side = str(od.get("side", "")).upper()
        qty = float(od.get("filled_qty") or 0.0)
        px = float(od.get("filled_avg_price") or 0.0)
        ccy = symbol_ccy(sym)
        rate = fx if ccy == "USD" else 1.0
        notional = qty * px * rate
        reason = o.reason if o else "sync"
        return Fill(
            date=od.get("filled_at", date)[:10] if od.get("filled_at") else date,
            symbol=sym, side=side, qty=qty, price=round(px, 6), ccy=ccy, fx=rate,
            fee_jpy=0.0,  # Alpaca米国株は手数料0(売却時の規制手数料は僅少・別途)
            notional_jpy=round(notional, 2), reason=reason,
            client_order_id=od.get("client_order_id", ""),
            broker_order_id=od.get("id", ""))

    def execute(self, orders: list[Order], prices: dict[str, float], fx: float,
                cash_jpy: float, date: str) -> tuple[list[Fill], list[tuple[Order, str]]]:
        fills: list[Fill] = []
        rejects: list[tuple[Order, str]] = []
        # 売り→買いの順(売却代金を買付余力に回す)
        for o in sorted(orders, key=lambda x: 0 if x.side == "SELL" else 1):
            if symbol_ccy(o.symbol) != "USD":
                rejects.append((o, "AlpacaBrokerは米国株(USD建て)のみ"))
                continue
            coid = self._client_order_id(o, date)
            try:
                submitted = self._submit(o, coid)
                od = self._poll(submitted.get("id", ""))
            except BrokerError as e:
                rejects.append((o, str(e)))
                continue
            st = od.get("status")
            if st == _FILLED and float(od.get("filled_qty") or 0) > 0:
                fills.append(self._fill_from_order(od, o, fx, date))
            elif st in _TERMINAL_FAIL:
                rejects.append((o, f"未約定({st}): {od.get('client_order_id', coid)}"))
            else:
                # タイムアウト(市場閉場など)。注文は working のまま。sync-fills で後刻反映。
                rejects.append((o, f"未約定(保留中: {st}) — 後刻 sync-fills で反映 [{coid}]"))
        return fills, rejects


class KabuStationBroker:
    """日本株の実弾ブローカー(Phase 3で実装)。"""

    def __init__(self, cfg, http=None):
        raise BrokerError(
            "日本株の実弾取引は未実装です(Phase 3)。docs/03_broker_and_data_setup.md 参照。")


# =====================================================================
# ファクトリ + ライブ多重ゲート
# =====================================================================

_LIVE_BROKERS = {"alpaca": AlpacaBroker, "kabu": KabuStationBroker}


def require_live_confirmation(env: dict | None = None) -> None:
    """環境変数 SMZ_LIVE_CONFIRM が確認フレーズと一致するか検証(docs/02 R8)。"""
    env = os.environ if env is None else env
    if env.get("SMZ_LIVE_CONFIRM", "") != LIVE_CONFIRM_PHRASE:
        raise BrokerError(
            "ライブ発注は未確認です。config を live にしただけでは発注しません。\n"
            f'  実弾を有効化するには環境変数を設定: export SMZ_LIVE_CONFIRM="{LIVE_CONFIRM_PHRASE}"\n'
            "  (docs/02_risk_policy.md R8 / docs/04_operations_runbook.md の実弾移行手順)")


def make_broker(cfg, http=None):
    """設定に応じたブローカーを生成。ライブは多重ゲートを通過した時のみ。"""
    if cfg.trading == "paper":
        return PaperBroker(cfg)
    if cfg.trading == "live":
        require_live_confirmation()
        adapter = _LIVE_BROKERS.get(cfg.live_broker)
        if adapter is None:
            raise BrokerError(
                f"mode.live_broker='{cfg.live_broker}' は不明です。"
                f"利用可能: {', '.join(sorted(_LIVE_BROKERS))}")
        return adapter(cfg, http=http) if http is not None else adapter(cfg)
    raise BrokerError(f"mode.trading='{cfg.trading}' は不正です(paper|live)")
