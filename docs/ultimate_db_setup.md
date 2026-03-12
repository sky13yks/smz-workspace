# 最新DB自動構築スクリプト (UX主導・15テーブル版)

ご承認いただいた最新のER図（AppSheet UX主導、機械・工具メンテの分離、製造番号ベースの管理）に基づき、スプレッドシート上に必要なすべてのテーブル（シート）を一括生成するGASスクリプトです。

---

## 1. データベース再構築の手順
現在のスプレッドシートのシートをすべて削除するか、新しいスプレッドシートを用意した上で、以下の手順を実行してください。

### 【コードの実行方法】
1. Apps Scriptエディタを開きます（既存のコードがある場合はすべて削除します）。
2. 以下のコードをコピーして貼り付け、保存します。
3. `initializeUltimateDatabase` 関数を選択して「実行」ボタンを押します。

```javascript
/**
 * 案件管理システム（UX主導・メンテ特化版） データベース初期構築スクリプト
 * ER図に基づく15個のテーブル（シート）を生成し、カラーリングと列幅を最適化します。
 */
function initializeUltimateDatabase() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 15テーブルの定義配列
  const sheetsDef = [
    // ==========================================
    // トランザクション（AppSheetでの入力起点）
    // ==========================================
    {
      name: "1. 活動ログ (DealsLogs)",
      headers: [
        "ログID", "件名_概要", "大分類", "アクション", "会社ID", 
        "担当者ID", "発生日時", "備考_メモ"
      ],
      bgColor: "#ead1dc", // 赤紫系（起点となる重要テーブル）
      widthMap: {2: 250, 8: 300}
    },
    {
      name: "2. 機械メンテ (MachineMaint)",
      headers: [
        "メンテID", "機械ID", "ログID", "作業日", "作業ステータス", "総括メモ"
      ],
      bgColor: "#d9d2e9" // 紫系
    },
    {
      name: "3. 機械メンテ詳細 (MaintDetails)",
      headers: [
        "詳細ID", "メンテID", "現場写真_URL", "作業メモ"
      ],
      bgColor: "#d9d2e9",
      widthMap: {4: 300}
    },
    {
      name: "4. 工具メンテ (ToolMaint)",
      headers: [
        "メンテID", "工具製造番号", "ログID", "研磨量", "コーティング膜種", 
        "算出価格", "価格補正理由", "次回メンテ推奨日"
      ],
      bgColor: "#c9daf8" // 青系
    },
    {
      name: "5. 見積_注文書 (EstimateOrders)",
      headers: [
        "書類ID", "ログID", "書類種別", "件名", "提出日", "有効期限", 
        "合計金額", "PDFファイルURL", "備考"
      ],
      bgColor: "#d0e0e3", // 水色系
      widthMap: {4: 200, 8: 250}
    },
    {
      name: "6. 書類明細 (LineItems)",
      headers: [
        "明細ID", "書類ID", "項目名_作業内容", "数量", "単位", "単価", "金額", "備考"
      ],
      bgColor: "#d0e0e3",
      widthMap: {3: 250}
    },
    {
      name: "7. 契約_仕様書 (ContractsSpecs)",
      headers: [
        "書類ID", "ログID", "書類種別", "対象機械_機器名", "取引条件_特記事項", 
        "添付ファイルURL"
      ],
      bgColor: "#d0e0e3",
      widthMap: {5: 300, 6: 250}
    },
    
    // ==========================================
    // マスター（静的データ / 資産情報）
    // ==========================================
    {
      name: "M0. メニューボタン (Launcher)",
      headers: [
        "ボタンID", "ボタン名", "アイコン_画像URL", "遷移先ビュー名", "大分類_セット値", "アクション_セット値", "表示順"
      ],
      bgColor: "#f4cccc", // 薄い赤（UI用ダミーテーブル）
      widthMap: {2: 200, 3: 200, 4: 200}
    },
    {
      name: "M1. 顧客_仕入先 (Companies)",
      headers: [
        "会社ID", "会社名", "会社名カナ", "取引区分", "郵便番号", "住所表記", 
        "電話番号", "FAX番号", "WebサイトURL", "備考"
      ],
      bgColor: "#fff2cc" // 黄色系
    },
    {
      name: "M2. 名刺 (Contacts)",
      headers: [
        "名刺ID", "会社ID", "部署名", "役職", "氏名", "氏名カナ", 
        "メールアドレス", "直通電話", "携帯電話", "退職フラグ", "備考"
      ],
      bgColor: "#fff2cc"
    },
    {
      name: "M3. スタッフ (Staff)",
      headers: [
        "担当者ID", "氏名", "所属部署", "メールアドレス", "電子印影URL", "退職フラグ"
      ],
      bgColor: "#fce5cd" // オレンジ系
    },
    {
      name: "M4. ワーク諸元 (WorkSpecs)",
      headers: [
        "諸元ID", "ワーク名称", "ワーク図面URL", "材質", "硬度", "備考"
      ],
      bgColor: "#efefef", // グレー系
      widthMap: {3: 250}
    },
    {
      name: "M5. 工具マスタ (Tools)",
      headers: [
        "製造番号", "仕入先_会社ID", "納品先_会社ID", "諸元ID", "工具名称", 
        "工具図面URL", "材質", "ピッチ", "圧力角", "ねじれ方向", "条数", 
        "外径", "厚み", "内径", "備考"
      ],
      bgColor: "#d9ead3", // 緑系
      widthMap: {5: 200, 6: 250}
    },
    {
      name: "M6. 機械マスタ (Machines)",
      headers: [
        "機械ID_製造番号", "会社ID", "機械名称", "メーカー", "型式", "年式", 
        "導入日", "仕様書URL", "備考"
      ],
      bgColor: "#d9ead3",
      widthMap: {3: 200}
    },
    {
      name: "M7. 工具価格マスタ (ToolPricing)",
      headers: [
        "価格ID", "外径_以上", "外径_未満", "厚み_以上", "厚み_未満", 
        "基本研磨価格", "基本コーティング価格"
      ],
      bgColor: "#efefef"
    },
    {
      name: "M8. 設定マスタ (Settings)",
      headers: [
        "設定キー", "設定値", "説明"
      ],
      bgColor: "#efefef"
    }
  ];

  // シートの生成とフォーマット
  sheetsDef.forEach(def => {
    let sheet = ss.getSheetByName(def.name);
    if (!sheet) {
      sheet = ss.insertSheet(def.name);
    } else {
      // 既存シートの場合は一度クリアして再構築（データ保護のため通常は非推奨ですが初期構築用として）
      sheet.clear();
    }
    
    // ヘッダー書き込み
    sheet.getRange(1, 1, 1, def.headers.length).setValues([def.headers]);
    sheet.getRange(1, 1, 1, def.headers.length)
      .setFontWeight("bold")
      .setBackground(def.bgColor)
      .setBorder(true, true, true, true, true, true);
    
    // ヘッダー行の固定
    sheet.setFrozenRows(1);
    
    // 列幅の調整
    if (def.widthMap) {
      for (let col in def.widthMap) {
        sheet.setColumnWidth(parseInt(col), def.widthMap[col]);
      }
    }
  });

  // 不要な初期シート「シート1」などがあれば削除（エラー回避のためtry-catch）
  try {
    const sheet1 = ss.getSheetByName("シート1");
    if (sheet1) ss.deleteSheet(sheet1);
  } catch(e) {}

  SpreadsheetApp.getUi().alert("UX主導型・全15テーブルの初期構築が完了しました。\nAppSheetでの読み込みとリレーション設定に進んでください。");
}
```

---

## 2. 次のアクション（AppSheet側での設定）

このスクリプトを実行してスプレッドシート側に15個のテーブルが完成したら、AppSheetエディタを開いて以下の設定を行います。ここからが本格的なアプリ構築フェーズになります。

1. **テーブルの追加**: 「Data」メニューから、15個すべてのテーブルをAppSheetにAddします。
2. **リファレンス（紐付け）の設定**: 
    - `活動ログ` テーブルの `会社ID` をRef型にし、参照先を `M1. 顧客_仕入先` にします。
    - `機械メンテ詳細` の `メンテID` をRef型にし、参照先を `2. 機械メンテ` にし、**「Is a part of」**にチェックを入れます（これにより写真フォームが親画面に埋め込まれます）。
3. **動的表示（Show_If）の設定**:
    - AppSheetの画面設定で、`大分類` に「修理」を選んだ時だけ `4. 機械メンテ` の入力項目が表示されるような動的UXを組んでいきます。
