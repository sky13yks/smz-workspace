# SMZ Trader — AI株式運用エージェント

**¥200,000 → ¥10,000,000 / 15年**を目標とする、個人向けシステマティック株式運用システム。
ルールベース戦略(トレンドフィルタ+モメンタム)が売買判断を行い、AI(Claude)が
リスクレビューと運用補佐を担当する。**現物のみ・借金なし・出金自由・フェイルセーフ設計**。

> ⚠️ 投資は自己責任です。このシステムは利益を保証しません。
> まず [docs/00_master_plan.md](docs/00_master_plan.md) の「ゴールの数学」を読んでください。

## クイックスタート(ペーパートレード)

```bash
cd trading-agent
pip install -e .                                   # 依存ゼロ(Python 3.11+)
smz-trader fetch-data                              # データ疎通確認(Stooq)
smz-trader deposit 200000 --note "ペーパー開始"
smz-trader run-daily                               # 日次サイクル(毎営業日)
smz-trader status
smz-trader backtest --start 2015-01-01 --end 2026-07-01
```

インストールせずに使う: `PYTHONPATH=src python3 -m smz_trader <command>`

AIレビューを有効化(任意): `pip install -e ".[ai]"` + `ANTHROPIC_API_KEY` を設定。
未設定でもシステムはルールベースで完結する。

## いま何ができるか(Phase 0 完了時点)

- ✅ ペーパートレード一式: 日次評価 / 月次リバランス / 約定シミュレーション
- ✅ リスクガードレール: 現金超過・空売り・ホワイトリスト外の拒否、DD25%/月次10%/資産5万円のサーキットブレーカー
- ✅ ハッシュ連鎖台帳(改竄検出・税務資料)、TWR成績評価、入出金自由
- ✅ バックテスト(本番と同一コード・決定論)
- ✅ AIリスクレビュー(Claude、買い注文のveto/縮小のみ可能)
- ✅ 実弾ブローカーアダプタ(Alpaca米国株)+接続確認/残高照合/後刻約定反映。多重安全ゲートで保護
- ⬜ 実弾での本番入金(Phase 2。口座開設・並走テスト・ゲート通過が前提。docs/03・04 参照)

## ドキュメント

| ファイル | 内容 |
|---|---|
| [docs/00_master_plan.md](docs/00_master_plan.md) | **15年マスタープラン**(目標の数学・フェーズとゲート・戦略仕様・プレイブック) |
| [docs/01_architecture.md](docs/01_architecture.md) | システム設計(決定論・フェイルセーフ・依存最小) |
| [docs/02_risk_policy.md](docs/02_risk_policy.md) | リスクポリシー正典(全ルール↔実装の対応表) |
| [docs/03_broker_and_data_setup.md](docs/03_broker_and_data_setup.md) | 証券会社・データソースの選定と開設手順 |
| [docs/04_operations_runbook.md](docs/04_operations_runbook.md) | 日次/月次/年次の運用手順・緊急対応・税務 |

## テスト

```bash
cd trading-agent
python3 -m unittest discover -s tests    # 42 tests
```

## 構成

```
trading-agent/
├── config/config.toml   # 戦略・リスクの全設定
├── src/smz_trader/      # 本体(標準ライブラリのみ)
├── tests/               # ユニット+統合テスト
├── docs/                # 計画・運用ドキュメント
└── state/               # 実行時状態(Git管理外): 台帳・キャッシュ・レポート
```
