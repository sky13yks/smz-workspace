# 案件管理システム V4.0 - AppSheet 設定ガイド

スプレッドシート（DB）の作成が完了したのち、AppSheet上で**「どのカラム同士を繋ぐか（Ref）」「どのような自動計算をさせるか（Formula）」**を設定するための完全ガイドです。

---

## � 1. テーブル追加とリレーション (Ref) の設定

AppSheetエディタの `Data` > `Tables` から、作成した12個のシートを追加します。
その後、`Data` > `Columns` で各テーブルの参照関係（Ref）を設定します。

### T1_Deals (案件管理)
*   **顧客会社ID** `Type: Ref` -> `Source table: M1_Companies`
*   **仕入先会社ID** `Type: Ref` -> `Source table: M1_Companies`
*   **自社担当者ID** `Type: Ref` -> `Source table: M2_Contacts`
*   **親案件ID** `Type: Ref` -> `Source table: T1_Deals` (自己参照)

### T1D_DealItems (案件明細)
*   **案件ID** `Type: Ref` -> `Source table: T1_Deals`
    *   ✅ **Is a part of**: `ON` （案件を消したら明細も消える連携）
*   **諸元ID** `Type: Ref` -> `Source table: A2_WorkSpecs`
*   **個体ID** `Type: Ref` -> `Source table: A1_Assets`

### T2_Papers (帳票管理)
*   **案件ID** `Type: Ref` -> `Source table: T1_Deals`
    *   ✅ **Is a part of**: `ON`
*   **元帳票ID** `Type: Ref` -> `Source table: T2_Papers` (自己参照)
*   **相手先会社ID** `Type: Ref` -> `Source table: M1_Companies`

### T2D_PaperLines (帳票明細)
*   **帳票ID** `Type: Ref` -> `Source table: T2_Papers`
    *   ✅ **Is a part of**: `ON`
*   **案件明細ID** `Type: Ref` -> `Source table: T1D_DealItems`

### T5_Files (図面・資料管理)
*   **案件ID** `Type: Ref` -> `Source table: T1_Deals`
    *   ✅ **Is a part of**: `ON`
*   **個体ID** `Type: Ref` -> `Source table: A1_Assets`

### T6_WorkLogs (作業履歴)
*   **案件ID** `Type: Ref` -> `Source table: T1_Deals`
    *   ✅ **Is a part of**: `ON`
*   **個体ID** `Type: Ref` -> `Source table: A1_Assets`

---

## 🧮 2. 重要なカラムの設定ルール (Type, Initial Value, Formula)

### T1_Deals (案件管理)
*   **案件ID**
    *   **Initial value**: `"D-" & TEXT(TODAY(),"YYYYMMDD") & "-" & UNIQUEID()`
*   **ステータス**
    *   **Type**: `Enum` (引合, 見積作成中, 見積提出済, 受注・発注済, ...)
    *   **Initial value**: `"引合"`
*   **大分類**
    *   **Type**: `Enum` (工具販売, 加工受託, 新品機械, 中古機械, 修理, 工具メンテナンス)
*   **小分類**
    *   **Type**: `Enum`
    *   **Valid If**: 
        ```appsheet
        IFS(
          [大分類] = "工具販売", LIST("カタログ品", "受注生産"),
          [大分類] = "中古機械", LIST("買取", "販売"),
          [大分類] = "修理", LIST("メーカー委託", "同行修理", "業者委託"),
          [大分類] = "工具メンテナンス", LIST("研磨", "コーティング", "修理OH")
        )
        ```

### T6_WorkLogs (作業履歴) 🌟 コーティング価格表対応
*   **作業区分**
    *   **Type**: `Enum` (研磨, コーティング, 修理, オーバーホール, 点検)
*   **同行費用**
    *   **Formula**: `[同行日数] * ANY(SELECT(M4_Settings[設定値], [設定キー]="同行修理日額"))`
*   **算出価格** (価格マトリクス自動計算)
    *   **Formula**:
        ```appsheet
        IF([作業区分]="コーティング",
          ANY(
            ORDERBY(
              SELECT(
                M3_ToolPricing[基本価格],
                AND(
                  [区分] = "コーティング",
                  [コーティング種別] = [_THISROW].[コーティング膜種],
                  [直径_最大] >= Number([個体ID].[外径]),
                  [全長_最大] >= Number([個体ID].[厚み])
                )
              ),
              [直径_最大], FALSE,
              [全長_最大], FALSE
            )
          ) 
          * IF([DB処理有無]=TRUE, 1.2, 1.0) 
          * IF([除膜処理有無]=TRUE, 0.5, 1.0),
          0 // 研磨などの場合は別途ロジックを指定
        )
        ```

### T2_Papers (帳票管理)
*   **種別**
    *   **Type**: `Enum`
    *   **Values**: `仕入見積書`, `販売見積書`, `注文書`, `発注書`, `納品書`, `請求書`

---

## 🤖 3. AppSheet Automation (Bot) の設定

「書類(T5)アップロードで、案件(T1)のステータスを進めるBot」です。

1. **Automation > Bots** から `New Bot` を作成。
2. **Event**:
   - `Event name`: `T5 Upload Trigger`
   - `Data change type`: `Adds only`
   - `Table`: `T5_Files`
   - `Condition`: 
     ```appsheet
     IN([カテゴリ], {"仕入見積書", "販売見積書", "注文書", "発注書", "工具図面", "承認図", "納品書", "請求書"})
     ```
3. **Step (Process)**:
   - `Step name`: `Update Deal Status`
   - `Run a data action`: `Set row values`
   - `Table`: `T1_Deals` (※実際はT1側の設定アクションを呼び出すか、Lookupしてセットする設定を行います)
   - `Set these columns` > `ステータス`:
     ```appsheet
     IFS(
       [カテゴリ]="仕入見積書", "見積作成中",
       [カテゴリ]="販売見積書", "見積提出済",
       [カテゴリ]="注文書", "受注・発注済",
       [カテゴリ]="発注書", "受注・発注済",
       [カテゴリ]="工具図面", "承認図回程中",
       [カテゴリ]="承認図", "承認図確定",
       [カテゴリ]="納品書", "納品済",
       [カテゴリ]="請求書", "請求済"
     )
     ```

---

## 🚀 4. ランチャーボタンのアクション設定 (LINKTOFORM)

ホーム画面（ランチャー）のボタンをクリックした際、特定のフォームを開きつつ初期値をセットするアクション設定です。

1. **Actions** > **New Action**
2. **Action name**: ランチャー実行
3. **For a record of this table**: `L1_Launcher`
4. **Do this**: `App: go to another view within this app`
5. **Target**:
   ```appsheet
   LINKTOFORM(
     [遷移先ビュー名],
     "大分類", [大分類セット値],
     "小分類", [小分類セット値]
   )
   ```
   > 💡 **値がうまく引き継がれない場合**：遷移先のフォーム（例: `T1_Deals_Form`）で、「大分類」や「小分類」の設定（Data > Columns）が `Show?` (表示する) になっているか、また `Editable?` (編集可能) になっているか確認してください。非表示の項目には値が入りません。
6. **Appearance > Prominence**: `Do not display`

これを **Views > ランチャー画面 > Behavior > Row Selected** に割り当てれば完成です！
