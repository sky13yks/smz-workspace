# 運用ランブック

## 0. 初期セットアップ(1回だけ)

```bash
cd trading-agent
# (任意) pipでインストール。しなくても PYTHONPATH=src python3 -m smz_trader で動く
pip install -e .              # コアのみ(依存ゼロ)
pip install -e ".[ai]"        # AIレビューも使う場合

# APIキー(AIレビュー用、任意)
cp config/secrets.env.example config/secrets.env  # 編集して ANTHROPIC_API_KEY を設定
set -a; source config/secrets.env; set +a

# データ疎通確認 → ペーパー開始
smz-trader fetch-data
smz-trader deposit 200000 --note "ペーパー開始"
smz-trader run-daily
```

## 1. 日次オペレーション(自動化推奨)

**実行タイミング**: 米国市場クローズ後 = 日本時間 朝6〜9時台に1回。
土日・休場日は「新しいバーなし」として自動で何もしない(冪等)。

### ローカル(Dev Container / 自宅マシン)での自動化

```bash
crontab -e
# 平日 08:10 JST に実行(TZがJSTのマシン)
10 8 * * 1-5  cd /path/to/trading-agent && set -a && . config/secrets.env && set +a && \
  PYTHONPATH=src python3 -m smz_trader run-daily >> state/cron.log 2>&1
```

### Claude Code クラウド環境での自動化(任意)

この環境のネットワーク方針は市場データドメインをブロックしている(2026-07-11時点)。
使う場合は環境設定で以下のドメインを許可してから、Claudeに「日次ルーチンを有効化して」と依頼:

```
stooq.com            # 価格データ(必須)
api.anthropic.com    # AIレビュー(既に許可済み)
```

補足: 無効化状態の日次Routine(トリガー)を作成してある場合は、有効化するだけでよい。

## 2. コマンド一覧

| コマンド | 用途 |
|---|---|
| `smz-trader status` | 現在の資産・ポジション・停止状態 |
| `smz-trader run-daily [--dry] [--offline] [--force-rebalance]` | 日次サイクル |
| `smz-trader deposit <円> [--note]` | 入金記録(積立もこれ) |
| `smz-trader withdraw <円> [--execute-sells]` | 出金(不足時は売却プラン提示/実行) |
| `smz-trader report` | 最新日次レポート表示 |
| `smz-trader backtest --start YYYY-MM-DD --end YYYY-MM-DD [--cash N]` | バックテスト |
| `smz-trader halt [--reason X]` | **緊急停止(いつでも使ってよい)** |
| `smz-trader resume [--acknowledge]` | 再開 |
| `smz-trader verify-ledger` | 台帳の改竄検査 |
| `smz-trader fetch-data` | 全銘柄キャッシュ更新 |

## 3. 月次レビュー(15分・毎月第1土曜など固定)

- [ ] `smz-trader status` と当月レポートを確認
- [ ] `smz-trader verify-ledger` → OK
- [ ] 拒否注文・ブレーカー発動があれば妥当性を確認(docs/02と突合)
- [ ] `state/ledger.jsonl` をGoogle Driveへバックアップ(コピーするだけ)
- [ ] 今月の積立額を決めて `deposit`(任意)
- [ ] 気になる点はClaude Codeに「月次レビューして」と依頼(レポート/台帳を読ませる)

## 4. 年次レビュー(1時間・毎年7月)

- [ ] TWR指数 vs SPY円換算買い持ちの比較(バックテストコマンドで再現)
- [ ] docs/00 §7 マイルストーン表と照合 → Plan A/B の進捗判定
- [ ] docs/00 §0(大前提)と §1(数学)を音読
- [ ] パラメータ変更の検討(年1回まで。変更は docs/02 R7 の手続きで)
- [ ] 税務準備(下記)
- [ ] 家族向け手順書(§6)の更新

## 5. 税務チェックリスト(毎年1〜2月)

- 実弾移行後: 海外ブローカー(IBKR等)は特定口座がないため**確定申告が必要**。
  - 台帳の FILL イベントが譲渡損益計算の一次資料(取得原価は台帳の cost 追跡を使用)
  - 米国株の配当は日米租税条約で源泉10% → 外国税額控除
  - 為替差損益にも留意(円転時)
- 国内ブローカー(kabuステーション等)なら特定口座(源泉徴収あり)で申告簡略化可
- 迷ったら税理士に台帳エクスポートを渡す(それができる形式で記録されている)

## 6. 家族向け緊急手順書(印刷して保管)

> 山口朔矢が対応できない状況でこの運用を止めたい場合:
> 1. PCの `trading-agent` フォルダで: `smz-trader halt --reason "family stop"`
>    (これで新規売買は一切行われません)
> 2. 全て現金化したい場合: `smz-trader withdraw 99999999 --execute-sells`
> 3. 実弾運用中の場合、証券会社(口座情報: ここに記入____________)に電話し、
>    本人確認の上「全売却と出金」を依頼(相続手続きは証券会社の案内に従う)
> 4. わからなければ何もしなくてよい(借金になることは仕組み上ありません)

## 7. 障害対応

| 症状 | 対応 |
|---|---|
| `no_data` が3日以上続く | Stooq側の問題の可能性 → docs/03の代替プロバイダに切替(config.tomlの[data]) |
| `verify-ledger` が✗ | **触らず**バックアップと差分確認。原因不明ならペーパーは inception からリプレイで再構築 |
| ブレーカー発動 | まず何もしない(それが正常動作)。docs/02を読み、月次レビューで再開判断 → `resume` |
| 実弾で誤発注疑い | `halt` → ブローカー画面で実残高確認 → 台帳と突合 → 原因究明までペーパーに戻す |
| PCが壊れた | 新環境にリポジトリをclone → ledger.jsonlのバックアップを state/ に復元 → 再開 |

## 8. やってはいけないこと

- ドローダウン中の設定緩和・「取り返す」ための手動売買(docs/02 R7)
- 台帳ファイルの手動編集(ハッシュ連鎖が壊れ、システムが停止する。それが正しい動作)
- secrets.env のコミット
- ブレーカー発動直後の即時 resume(最低一晩置く)
