# SMZ 受発注管理システム — Claude Code 指示書

株式会社清水商會 / 担当：山口 朔矢

---

## プロジェクト概要

加工受託・歯車切削工具・新品中古工作機械を扱う商社の受発注管理システム。
**AppSheet + Google Apps Script + Google Spreadsheets** で構築。

---

## アーキテクチャ

| レイヤー | 技術 | 場所 |
|---------|------|------|
| UI | AppSheet | Google Cloud |
| バックエンド | Google Apps Script (GAS) | `gas/` フォルダ |
| DB | Google Spreadsheets (18シート) | Google Drive |
| ファイル | Google Drive 共有ドライブ | `/図面保管/` |
| 開発環境 | Docker Dev Container + clasp | `.devcontainer/` |

---

## GASファイル構成（`gas/` フォルダ）

| ファイル | 役割 |
|---------|------|
| `Code.gs` | 旧エントリーポイント（doPost_legacy_v1 に改名済み） |
| `v4_db_setup.gs` | 全16テーブル一括生成スクリプト（v5.0設計） |
| `v4_gas_core.gs` | **現役Webhookエントリーポイント** (doPost) + フォルダ作成 |
| `v4_gas_papers.gs` | 帳票（見積書・発注書・納品書・請求書）処理 |
| `v4_gas_v4_core.gs` | 旧フォルダ/PDF処理（legacy_v2 に改名済み） |
| `appsscript.json` | Apps Script マニフェスト |

⚠️ `doPost` は `v4_gas_core.gs` が唯一の本番エントリーポイント。他ファイルにdoPostを追加しないこと。

---

## スプレッドシートDB（v5.0 / 16シート）

### マスタ系
- `M1_Companies` — 会社マスタ（顧客・仕入先・修理業者共用）。`掛け率`列あり（工具メンテ販売価格 = 仕入価格 × 掛け率）
- `M2_Contacts` — 担当者マスタ（M1に所属）
- `M3_ToolPricing` — 工具メンテ価格表（外径×厚みのサイズ区分 × 作業種別の仕入単価マトリクス）
- `M4_Settings` — システム設定（定数・閾値）
- `M6_Tools` — 工具マスタ（よく扱うオーダーメイド工具の雛形）

### 資産系
- `A1_Assets` — 個体管理（工具・中古機械・新品機械の現物追跡）
- `A2_WorkSpecs` — ワーク諸元（何を削るかの技術仕様）

### トランザクション系
- `T1_Deals` — 案件管理ヘッダ（業務カテゴリ・ステータス・失注フラグ等）
- `T1D_DealItems` — 案件明細（1案件に複数品目）
- `T2_Papers` — 帳票管理（見積/発注/納品/請求 統合）
- `T2D_PaperLines` — 帳票明細行
- `T4_QuoteRequests` — 仕入見積依頼（形状バリアント単位）
- `T4D_QuoteResponses` — 仕入見積回答（複数メーカーの回答比較）
- `T5_Files` — 書類管理（Drive URLリンク集）
- `T6_WorkLogs` — 作業履歴（工具メンテ・修理の実績記録）
- `T7_RepairExpenses` — 修理・出張費用明細（高速代・日当・部品代等）

### システム系
- `L1_Launcher` — AppSheetランチャー（業務カテゴリ別ボタン）

---

## 採番ルール（重要）

| 種別 | 形式 | 例 |
|------|------|-----|
| 案件番号 | Y-YYMMDD-01 | Y-250310-01 |
| 見積番号 | Y-YYMMDD-Q01 | Y-250310-Q01 |
| 発注番号 | Y-YYMMDD-P01 | Y-250310-P01 |

※ Yは担当者イニシャル（担当者が増えた際は変更するだけ）

---

## 業務カテゴリとステータス遷移

T1_Deals.業務カテゴリ: オーダーメイド工具 / カタログ品工具 / 工具メンテナンス / 加工受託 / 機械修理 / 中古機械 / 新品機械販売

各カテゴリ共通ステータス（業務カテゴリによってスキップするステップがある）:
```
新規受付 → 仕入見積依頼中 → 販売見積作成中 → 見積提出済み
→ 受注確定 → 発注済み → 納品待ち → 納品済み → 請求済み → 完了

※ 失注はどのステップからも手動で遷移可能（T1_Deals.失注フラグ）
※ カタログ品工具は仕入見積依頼ステップをスキップ
※ 工具メンテナンスは見積→受注→作業完了→請求の短縮フロー
```

---

## ファイル管理ルール

- フォルダ: `共有ドライブ/図面保管/` のみ（フラット1階層）
- 命名規則: `{日付}_{顧客名}_{品名・規格}.pdf`
- 例: `20250310_ABC工業_エンドミルφ10x50L.pdf`
- ローカル保存なし（クラウド完結）

---

## よく使うコマンド（Dev Container内）

```bash
# GASにコードをアップロード
cd gas && clasp push

# GASからコードをダウンロード（差分確認用）
cd gas && clasp pull

# GASの実行ログを確認
cd gas && clasp logs

# GASのエディタをブラウザで開く
cd gas && clasp open
```

---

## Gitブランチ運用

```
main        ← 本番稼働中のコード（直接pushしない）
develop     ← 開発の統合ブランチ
feature/xxx ← 各自の作業ブランチ
```

### コミットメッセージ例（日本語OK）
```
feat: 工具マスタテーブルを追加
fix: 採番ロジックの連番ズレを修正
docs: v4_implementation_plan.mdを更新
test: PDF生成の動作テストを追加
```

---

## セキュリティルール（絶対厳守）

- `.clasp.json` は **Gitにpushしない**（スクリプトIDが含まれる）
- `.clasprc.json` は **Gitにpushしない**（Google認証トークン）
- GAS WebAppのデプロイは **「自分のみアクセス可能」** 設定
- スプレッドシートの共有は **会社ドメインのみ**

---

## 現在の優先TODO（2026-03-12時点）

🔴 最優先
1. v4_db_setup.gs (setupV4Database) をGASエディタで実行してDBを再構築
2. M3_ToolPricingのサンプル価格を実際の価格表PDFの値に更新
3. GAS動作テスト（createDealFolder / generatePaperPdf / copyPaperAndLines）
4. 納品書・請求書テンプレート作成（Googleスプレッドシート）

🟡 高優先
5. AppSheet Automation設定（業務カテゴリ別ステータス自動遷移）
6. AppSheet UIの最終調整（新テーブル・新カラム対応）

---

## 未決事項

- 工具番号の採番ルール（メーカー付番 or 社内独自採番）
- 加工案件の諸元設計（歯車/キー加工/非歯車加工の詳細）
- Matrix社機種マスタの設計

---

## 将来構想

- Looker Studio ダッシュボード（月次売上・案件別粗利率）
- メール自動送信（見積書・発注書PDF生成後）
- 会社HP連携（smz-HP / Next.js / Vercel）← A1_Assets在庫連動
- お問い合わせフォーム → T1_Deals への自動登録
- BigQuery移行（スプレッドシートDBの限界を超えた時）
