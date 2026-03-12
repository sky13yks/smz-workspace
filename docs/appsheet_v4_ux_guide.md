# AppSheet UX/UI 設定ガイド (v4.0 準拠)

本ガイドは、ユーザーが毎日触れる「使いやすい画面」の構築方法を定義します。

---

## 🟢 1. ランチャー画面（ホーム）の構築

ユーザーが最初に目にする、ボタン型のメニュー画面です。

1. **Table 追加**: `L1_Launcher` をデータソースとして追加します。
2. **View 作成**:
   - `View name`: `Home`
   - `For this data`: `L1_Launcher`
   - `View type`: **Gallery**
   - `Sort by`: `表示順` (Ascending)
   - `Image size`: `Medium`
3. **Behavior (Behavior > Actions)**:
   - ボタンをタップした時に指定のフォームを開く Action を作成します。
   - `Action name`: `Go to Form`
   - `For a record of this table`: `L1_Launcher`
   - `Do this`: `App: go to another view within this app`
   - `Target`: 
     ```appsheet
     LINKTOFORM(
       [遷移先ビュー名], 
       "大分類", [大分類セット値],
       "小分類", [小分類セット値]
     )
     ```
4. **Gallery の Event Action**:
   - View の `Event Actions > Row Selected` に上記 `Go to Form` を設定します。

---

## 🔵 2. 業務別の「動的フォーム」制御

T1（案件管理）の入力フォームを、大分類に応じて「必要な項目だけ」出す設定です。

`T1_Deals` の各カラムの `Show_If` に設定します：

- **諸元ID**: `IN([大分類], {"工具販売", "加工受託"})`
- **同行日数 / 同行費用**: `AND([大分類]="修理OH", [小分類]="同行修理")`
- **個体ID**: `OR([大分類]="修理OH", [大分類]="工具販売"([小分類]="メンテ"))`

---

## 🟡 3. ダッシュボード・スライスの活用

業務進捗を可視化するためのビューです。

### 締め日アラートビュー
- **Slice**: `T2_Papers_Slice_Delivery`
- **Filter condition**: `AND([種別]="納品書", [入金確認]=FALSE, [発行日] <= EOMONTH(TODAY(), -1))`
- **Purpose**: 先月以前に納品したが、まだ入金されていない（請求漏れ・入金待ち）案件を一覧表示。

### 承認図待ちビュー
- **Slice**: `T2_Papers_Slice_WaitApproval`
- **Filter condition**: `AND([種別]="発注書", [承認図面フラグ]=FALSE)`
- **Purpose**: メーカーに発注したが、まだ承認図が戻ってきていない案件を監視。

---

## 🟠 4. 表示ラベルのカスタマイズ (Display Label)

AppSheetの各テーブルの `Display name` を日本語に設定します：
- `T1_Deals` → **案件管理**
- `T2_Papers` → **見積・注文・請求**
- `A1_Assets` → **個体/機械図鑑**
- `A2_WorkSpecs` → **ワーク技術諸元**
