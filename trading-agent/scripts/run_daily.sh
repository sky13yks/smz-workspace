#!/usr/bin/env bash
# SMZ Trader 日次実行ラッパー(macOS/Linux/WSL/Git Bash)。
#
# cron / launchd / systemd timer から「1日1回このスクリプトを叩く」だけで済むように、
# 一時的なネットワーク障害(Wi-Fi再接続直後・スリープ復帰直後など)を吸収するリトライを
# 内蔵している。ここで諦めても翌日のスケジュール実行には一切影響しない
# (run-daily はデータが取れない日は「何もしない」フェイルセーフ設計のため)。
#
# 使い方:
#   ./scripts/run_daily.sh                # 通常実行
#   ./scripts/run_daily.sh --force-rebalance --dry   # smz-trader run-daily への追加引数はそのまま渡せる
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

STATE_DIR="$REPO_ROOT/state"
LOG_FILE="$STATE_DIR/cron.log"
mkdir -p "$STATE_DIR"

export PYTHONPATH="$REPO_ROOT/src"

# secrets.env があれば読み込む(AIレビュー用ANTHROPIC_API_KEY等。未設定でも動作する)
if [ -f "$REPO_ROOT/config/secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_ROOT/config/secrets.env"
  set +a
fi

MAX_RETRIES="${SMZ_DAILY_MAX_RETRIES:-3}"
RETRY_DELAY="${SMZ_DAILY_RETRY_DELAY:-90}"  # 秒

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

attempt=1
while [ "$attempt" -le "$MAX_RETRIES" ]; do
  log "run-daily 開始 (試行 $attempt/$MAX_RETRIES)"
  python3 -m smz_trader --config "$REPO_ROOT/config/config.toml" run-daily "$@" >> "$LOG_FILE" 2>&1
  code=$?
  if [ "$code" -eq 0 ]; then
    log "run-daily 成功"
    exit 0
  fi
  log "run-daily 失敗(終了コード $code、試行 $attempt/$MAX_RETRIES)"
  if [ "$attempt" -lt "$MAX_RETRIES" ]; then
    log "${RETRY_DELAY}秒後にリトライします"
    sleep "$RETRY_DELAY"
  fi
  attempt=$((attempt + 1))
done

log "run-daily が ${MAX_RETRIES}回とも失敗しました。今日は諦めます" \
    "(フェイルセーフ設計のため資産への影響はありません。明日また自動で実行されます)"
exit 1
