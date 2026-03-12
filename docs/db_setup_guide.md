# Google Workspace 基幹DB 構築手順（ER図反映版）

作成したER図（設計図）に基づき、**「顧客名」ではなく「顧客ID」によるリレーション**を取り入れた、より堅牢なデータベース構築スクリプトに更新しました。

---

## 1. 構築するデータベースの構造

* **「案件管理DB」シート**: メインテーブル。顧客は「顧客ID」で紐付けます。
* **「顧客マスタ」シート**: 取引先を管理。各顧客に一意の「顧客ID」を持たせます。
* **「設定マスタ」シート**: 対象業務やステータスのドロップダウン選択肢。

---

## 2. 基幹DB自動構築スクリプトの実行

手作業でのシート・項目作成を省くため、以下のスクリプトをスプレッドシート（Google Apps Script）に貼り付けて実行してください。

### 【ステップ 1】 Apps Script の起動
1. 基幹DBとするGoogle スプレッドシートを開きます。
2. 上部メニューから **「拡張機能」 ＞ 「Apps Script」** をクリックします。

### 【ステップ 2】 ER図反映版・構築スクリプトの貼り付け
1. 開いたエディタの `コード.gs` の内容をすべて消去します。
2. 以下のコードをコピーして貼り付け、保存（Ctrl+S または Cmd+S）します。

```javascript
/**
 * 歯車業界向け 案件管理DB（ER図反映版）の初期構築スクリプト
 */
function initializeCoreDatabase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // ============================================
  // 1. 案件管理DB シートの作成
  // ============================================
  let projectDbSheet = ss.getSheetByName("案件管理DB");
  if (!projectDbSheet) {
    projectDbSheet = ss.insertSheet("案件管理DB", 0);
  }
  
  // ※顧客名を「顧客ID」に変更し、AppSheetでリレーションを組めるようにしています
  const projectHeaders = [
    "案件ID", "案件名", "対象業務", "ステータス", "顧客ID", 
    "担当者", "受注予定日", "納品予定日", 
    "ドライブフォルダURL", "図面ファイルURL", "見積書URL", "承認図URL", "仕様書・報告書URL",
    "備考", "登録日時", "最終更新日時"
  ];
  projectDbSheet.getRange(1, 1, 1, projectHeaders.length).setValues([projectHeaders]);
  // ヘッダーの装飾
  projectDbSheet.getRange(1, 1, 1, projectHeaders.length)
    .setFontWeight("bold")
    .setBackground("#d9ead3")
    .setBorder(true, true, true, true, true, true);
  projectDbSheet.setFrozenRows(1);
  // 列幅の調整（見やすくするため）
  projectDbSheet.setColumnWidth(2, 250); // 案件名
  projectDbSheet.setColumnWidth(9, 300); // フォルダURL

  // ============================================
  // 2. 顧客マスタ シートの作成
  // ============================================
  let customerSheet = ss.getSheetByName("顧客マスタ");
  if (!customerSheet) {
    customerSheet = ss.insertSheet("顧客マスタ", 1);
  }
  
  const customerHeaders = ["顧客ID", "顧客名", "担当部署", "担当者名", "備考"];
  customerSheet.getRange(1, 1, 1, customerHeaders.length).setValues([customerHeaders]);
  customerSheet.getRange(1, 1, 1, customerHeaders.length)
    .setFontWeight("bold")
    .setBackground("#fff2cc");
  customerSheet.setFrozenRows(1);
  
  // サンプルデータ
  const sampleCustomers = [
    ["C-001", "〇〇歯車工業", "製造部", "山田 太郎", ""],
    ["C-002", "株式会社△△精機", "購買部", "鈴木 一郎", ""]
  ];
  customerSheet.getRange(2, 1, sampleCustomers.length, sampleCustomers[0].length).setValues(sampleCustomers);

  // ============================================
  // 3. 設定マスタ シートの作成
  // ============================================
  let masterSheet = ss.getSheetByName("設定マスタ");
  if (!masterSheet) {
    masterSheet = ss.insertSheet("設定マスタ", 2);
  }
  
  const masterHeaders = ["対象業務", "ステータス区分"];
  masterSheet.getRange(1, 1, 1, masterHeaders.length).setValues([masterHeaders]);
  masterSheet.getRange(1, 1, 1, masterHeaders.length)
    .setFontWeight("bold")
    .setBackground("#efefef");
  masterSheet.setFrozenRows(1);
  
  const businessTypes = [
    ["加工受託"], ["工具受注生産・メンテ"], ["一般工具販売"], 
    ["新品工作機械販売"], ["中古工作機械売買"], ["機械修理"]
  ];
  const statuses = [
    ["1_引合・図面確認中"], ["2_見積作成中（メーカー確認）"], ["3_見積提示済・検討中"], 
    ["4_受注済・発注済"], ["5_承認図回程中"], ["6_加工/製作/修理手配中"], 
    ["7_納品・検収待ち"], ["8_完了"], ["9_失注"]
  ];
  
  masterSheet.getRange(2, 1, businessTypes.length, 1).setValues(businessTypes);
  masterSheet.getRange(2, 2, statuses.length, 1).setValues(statuses);

  // 完了メッセージ
  SpreadsheetApp.getUi().alert("Google Workspace基幹DB（ER図反映版）の初期構築が完了しました。");
}
```

### 【ステップ 3】 スクリプトの実行
1. エディタ上部から `initializeCoreDatabase` を選択し、**「実行」** をクリックします。
2. （初回のみ）アクセス承認を行います。
3. スプレッドシートに反映されます。

---

## 3. 次のステップ（AppSheetでの連携）

このER図反映版で構築したシートを、AppSheetに取り込みます。

1. AppSheetエディタで **「Data」** > **案件管理DB** のView Columnsを開きます。
2. **顧客ID**（※先ほど顧客名だった箇所が「顧客ID」になっています）の型（Type）を **「Ref」** にします。
3. Source tableとして **「顧客マスタ」** を指定します。

これにより、AppSheet上ではドロップダウンで「顧客名」を選びつつ、裏側のスプレッドシートには「顧客ID」が正しく保存される堅牢なシステムになります。連携が終わりましたら自動フォルダ作成の設定に進みます！
