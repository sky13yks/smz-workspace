# 本格的データベース構築 ＆ GASファイル構成

プランに沿って、7つのテーブルを持つ本格的なデータベース構築スクリプトと、GASの分割モジュール（土台）を用意しました。

---

## 1. データベース構築のやり直し

前回作成したスプレッドシートのシートをすべて削除（または新しいスプレッドシートを用意）し、以下のスクリプトを実行してDBを作り直してください。

### コード1：`db_initializer.gs` (初期構築スクリプト)
Apps Scriptエディタを開き、左側メニューの `+` ボタンから「スクリプト」を選んで新しく `db_initializer.gs` というファイル名で作成し、以下のコードを貼り付けて実行します。

```javascript
/**
 * 案件管理システム（本格版） データベース初期構築スクリプト
 * 7つのテーブル（シート）を生成します。
 */
function initializeAdvancedDatabase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetsDef = [
    {
      name: "案件 (Deals)",
      headers: [
        "案件ID", "案件名", "対象業務", "ステータス", "会社ID", 
        "自社担当者ID", "受注予定日", "納品予定日", "ドライブフォルダURL", 
        "利益額", "利益率", "備考", "登録日時", "最終更新日時"
      ],
      widthMap: {2: 250, 9: 300},
      bgColor: "#d9ead3" // 緑系
    },
    {
      name: "品目 (Items)",
      headers: [
        "品目ID", "案件ID", "商品種別", "商品名・規格", "メーカー", "数量", "単位",
        "仕入単価", "販売単価", "粗利", "図面ファイルURL", "備考"
      ],
      widthMap: {4: 250},
      bgColor: "#c9daf8" // 青系
    },
    {
      name: "取引先 (Companies)",
      headers: [
        "会社ID", "会社名", "会社名カナ", "郵便番号", "住所", "電話番号", 
        "FAX番号", "WebサイトURL", "取引区分", "備考"
      ],
      bgColor: "#fff2cc" // 黄色系
    },
    {
      name: "名刺 (Contacts)",
      headers: [
        "名刺ID", "会社ID", "部署名", "役職", "氏名", "氏名カナ", "メールアドレス", 
        "直通電話", "携帯電話", "備考"
      ],
      bgColor: "#fce5cd" // オレンジ系
    },
    {
      name: "工具 (Tools)",
      headers: [
        "工具ID", "案件ID", "工具名称", "メーカー", "図面URL", "承認図URL", 
        "ステータス", "新品購入日", "次回メンテ推奨日", "備考"
      ],
      bgColor: "#ead1dc" // ピンク系
    },
    {
      name: "工具メンテナンス (Maint History)",
      headers: [
        "履歴ID", "工具ID", "案件ID", "作業区分", "作業内容", "作業日", 
        "担当者", "作業前写真", "作業後写真", "備考"
      ],
      bgColor: "#d9d2e9" // 紫系
    },
    {
      name: "スタッフ (Staff)",
      headers: [
        "担当者ID", "氏名", "所属部署", "メールアドレス", "電子印影URL", "退職フラグ"
      ],
      bgColor: "#efefef" // グレー系
    }
  ];

  sheetsDef.forEach(def => {
    let sheet = ss.getSheetByName(def.name);
    if (!sheet) {
      sheet = ss.insertSheet(def.name);
    }
    
    // ヘッダー書き込み
    sheet.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
    sheet.getRange(1, 1, 1, def.headers.length)
      .setFontWeight("bold")
      .setBackground(def.bgColor)
      .setBorder(true, true, true, true, true, true);
    sheet.setFrozenRows(1);
    
    // 列幅調整
    if (def.widthMap) {
      for (let col in def.widthMap) {
        sheet.setColumnWidth(parseInt(col), def.widthMap[col]);
      }
    }
  });

  SpreadsheetApp.getUi().alert("本格版データベース（7テーブル）の初期構築が完了しました。");
}
```

---

## 2. GASの分割モジュール（土台）

Apps Scriptエディタでファイルを分割して作成します。まずはモジュールの枠組みと、自動採番のロジックを作成します。

### コード2：`config.gs` (全体設定)
GASエディタで `+` から `config.gs` を作成し以下を貼り付けます。

```javascript
/** ==============================================
 * config.gs: システム全体の設定ファイル
 * ============================================== */
const CONFIG = {
  // 自動作成するGoogleドライブの親フォルダID
  DRIVE_PARENT_FOLDER_ID: "ここに親フォルダのIDをいれる", 
  
  // マージンチェック（利益率）の警告閾値
  MARGIN_WARNING_PERCENT: 15, // 15%未満の場合は警告
  
  // 各シート名
  SHEETS: {
    DEALS: "案件 (Deals)",
    ITEMS: "品目 (Items)",
    COMPANIES: "取引先 (Companies)",
    CONTACTS: "名刺 (Contacts)"
  }
};
```

### コード3：`idGenerator.gs` (ID自動採番ロジック)
`idGenerator.gs` を作成し以下を貼り付けます。提案書に合わせた `YYMMDD-Deal-XXXX` 形式を生成します。

```javascript
/** ==============================================
 * idGenerator.gs: ID自動採番・管理モジュール
 * ============================================== */

const IdGenerator = {
  /**
   * 新しい案件IDを生成する (例: 240315-Deal-0001)
   */
  generateDealId: function(sheet) {
    const today = new Date();
    const yy = String(today.getFullYear()).slice(-2);
    const mm = ("0" + (today.getMonth() + 1)).slice(-2);
    const dd = ("0" + today.getDate()).slice(-2);
    const datePrefix = yy + mm + dd; // 例: 240315
    
    // 当日の案件数をカウントして連番を生成する簡易ロジック
    // （本格運用の場合はID管理専用シートを使うことで重複を完全に防ぎますが、まずは簡易実装）
    const data = sheet.getDataRange().getValues();
    let todayCount = 0;
    
    // 1行目はヘッダーなので2行目から
    for (let i = 1; i < data.length; i++) {
      const id = String(data[i][0]).trim();
      if (id.startsWith(datePrefix + "-Deal-")) {
        todayCount++;
      }
    }
    
    const nextNum = ("000" + (todayCount + 1)).slice(-4);
    return `${datePrefix}-Deal-${nextNum}`;
  },
  
  /**
   * その他のテーブルのID生成 (例: ITEM-XXXX)
   */
  generateGenericId: function(prefix, prefixLength = 6) {
    // タイムスタンプとランダム文字列を組み合わせた重複しにくいID
    const ts = new Date().getTime().toString(36);
    const rnd = Math.random().toString(36).substring(2, prefixLength);
    return `${prefix}-${ts.slice(-4)}${rnd}`.toUpperCase();
  }
};
```

### コード4：`trigger.gs` (バックグラウンド処理の起点)
`trigger.gs` を作成し以下を貼り付けます。
前回と同様に「変更時」トリガーの登録が必要です。

```javascript
/** ==============================================
 * trigger.gs: AppSheet等からのデータ変更を検知
 * ============================================== */

function onSheetChange(e) {
  if (!e || !e.source) return;
  const sheet = e.source.getActiveSheet();
  const sheetName = sheet.getName();
  const row = e.range.getRow();
  
  // ヘッダーは除外
  if (row <= 1) return;

  const dataRange = sheet.getRange(row, 1, 1, sheet.getLastColumn());
  const rowData = dataRange.getValues()[0];

  /** --- 案件 (Deals) テーブルの処理 --- */
  if (sheetName === CONFIG.SHEETS.DEALS) {
    let currentId = rowData[0]; // A列: 案件ID
    let folderUrl = rowData[8]; // I列: ドライブフォルダURL
    let isUpdated = false;

    // 1. IDが空なら自動採番してセット
    if (!currentId || String(currentId).trim() === "") {
      const newId = IdGenerator.generateDealId(sheet);
      sheet.getRange(row, 1).setValue(newId);
      rowData[0] = newId;
      isUpdated = true;
    }
    
    // 2. ドライブフォルダ作成（TODO: 別途モジュール化箇所）
    // ...
  }
}
```

これらのコードを作成後、`db_initializer.gs` から `initializeAdvancedDatabase` を実行してください。
