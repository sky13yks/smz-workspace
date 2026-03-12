/**
 * ============================================================================
 * 案件管理システム V4.0 - スプレッドシート DB構築スクリプト (v4_db_setup.gs)
 * ============================================================================
 * 
 * 指定された設計に基づき、12個のテーブル（シート）とその見出し（1行目）を
 * 現在アクティブなスプレッドシートに一括で生成・上書きします。
 * 
 * 【使い方】
 * 1. 新規スプレッドシートを作成
 * 2. 拡張機能 > Apps Script を開く
 * 3. このコードを貼り付けて `setupV4Database` 関数を実行
 */

function setupV4Database() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // テーブル定義（シート名とカラムの配列）
  const tables = [
    {
      name: "M1_Companies",
      cols: ["会社ID", "会社名", "会社名カナ", "取引区分", "郵便番号", "住所", "電話番号", "FAX番号", "締日", "支払条件", "備考"]
    },
    {
      name: "M2_Contacts",
      cols: ["担当者ID", "会社ID", "氏名", "区分", "部署", "役職", "メール", "電話番号", "名刺画像", "電子印影URL", "退職/異動フラグ"]
    },
    {
      name: "M3_ToolPricing",
      // コーティング・価格表マトリクス対応済
      cols: ["価格ID", "区分", "コーティング種別", "直径_最大", "全長_最大", "基本価格", "DB処理割増率", "除膜処理掛率"]
    },
    {
      name: "M4_Settings",
      cols: ["設定キー", "設定値", "説明"]
    },
    {
      name: "A1_Assets",
      cols: ["個体ID", "個体名称", "個体区分", "所有会社ID", "メーカー会社ID", "諸元ID", "初回案件ID", "工具図面URL", "外径", "厚み", "内径", "材質", "累計研磨回数", "最終メンテ日", "型式", "年式", "仕様書URL", "備考"]
    },
    {
      name: "A2_WorkSpecs",
      cols: ["諸元ID", "ワーク名称", "加工区分", "モジュール/ピッチ", "圧力角", "ねじれ方向", "条数", "ワーク図面URL", "数量", "備考"]
    },
    {
      name: "T1_Deals",
      cols: ["案件ID", "案件名", "大分類", "小分類", "ステータス", "顧客会社ID", "仕入先会社ID", "自社担当者ID", "親案件ID", "発生日", "希望納期", "ドライブフォルダURL", "判断メモ", "備考"]
    },
    {
      name: "T1D_DealItems",
      cols: ["明細ID", "案件ID", "品名・内容", "諸元ID", "個体ID", "数量", "備考"]
    },
    {
      name: "T2_Papers",
      cols: ["帳票ID", "案件ID", "種別", "元帳票ID", "相手先会社ID", "発行日", "有効期限", "合計金額", "承認図面フラグ", "入金確認", "入金日", "複製フラグ", "備考"]
    },
    {
      name: "T2D_PaperLines",
      cols: ["明細ID", "帳票ID", "案件明細ID", "項目名", "数量", "単位", "単価", "金額", "備考"]
    },
    {
      name: "T5_Files",
      cols: ["資料ID", "案件ID", "個体ID", "ファイル名", "カテゴリ", "サフィックス", "ファイル", "登録日", "備考"]
    },
    {
      name: "T6_WorkLogs",
      cols: ["履歴ID", "案件ID", "個体ID", "作業区分", "作業日", "研磨量", "コーティング膜種", "DB処理有無", "除膜処理有無", "算出価格", "同行費用有無", "同行日数", "同行費用", "作業写真", "作業メモ"]
    },
    {
      name: "T4_QuoteRequests",
      // 見積依頼テーブル（サプライヤーへの仕入見積依頼を管理）
      cols: ["依頼ID", "案件ID", "仕入先会社ID", "担当者ID", "依頼日", "希望回答期限", "依頼内容", "依頼PDF_URL", "回答金額", "回答PDF_URL", "ステータス", "備考"]
    },
    {
      name: "M6_Tools",
      // 工具マスタテーブル（取扱工具の商品マスタ）
      cols: ["工具ID", "メーカー会社ID", "工具名称", "型式・品番", "工具区分", "材質", "コーティング", "外径", "全長", "仕様詳細", "標準単価", "備考", "カタログURL"]
    },
    {
      name: "L1_Launcher",
      cols: ["ボタンID", "ボタン名", "アイコン画像URL", "遷移先ビュー名", "大分類セット値", "小分類セット値", "表示順"]
    }
  ];

  // 各シートを作成または初期化
  tables.forEach(table => {
    let sheet = ss.getSheetByName(table.name);
    if (!sheet) {
      sheet = ss.insertSheet(table.name);
      Logger.log(`シート「${table.name}」を新規作成しました。`);
    } else {
      // 既存シートの中身をクリア（慎重に扱う場合はコメントアウトしてください）
      sheet.clear();
      Logger.log(`シート「${table.name}」を上書きクリアしました。`);
    }
    
    // 見出し行をセット
    sheet.getRange(1, 1, 1, table.cols.length).setValues([table.cols]);
    
    // 見出し行の書式設定（背景色、太字、中央揃え）
    const headerRange = sheet.getRange(1, 1, 1, table.cols.length);
    headerRange.setBackground("#4c1130").setFontColor("#ffffff").setFontWeight("bold").setHorizontalAlignment("center");
    
    // 枠線を引く＆列幅自動調整（簡易）
    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, table.cols.length);
  });

  // 初期不要シート(シート1)があれば削除
  const defaultSheet = ss.getSheetByName("シート1");
  if (defaultSheet && ss.getSheets().length > 1) {
    ss.deleteSheet(defaultSheet);
  }

  // 初期データの投入 (M4_Settings)
  const settingsSheet = ss.getSheetByName("M4_Settings");
  if (settingsSheet && settingsSheet.getLastRow() === 1) {
    const initialSettings = [
      ["同行修理日額", "50000", "同行修理時に発生する1日あたりの費用"],
      ["利益率警告閾値", "15", "粗利率がこれを下回るとアラート。単位%"],
      ["研磨回数アラート閾値", "5", "この回数を超えると新品提案リマインド"]
    ];
    settingsSheet.getRange(2, 1, initialSettings.length, 3).setValues(initialSettings);
  }

  // 初期データの投入 (L1_Launcher)
  const launcherSheet = ss.getSheetByName("L1_Launcher");
  if (launcherSheet && launcherSheet.getLastRow() === 1) {
    const initialLaunchers = [
      ["B-01", "🔧 工具販売を開始する", "https://img.icons8.com/color/48/drill.png", "T1_Deals_Form", "工具販売", "", 1],
      ["B-02", "🏭 加工受託を開始する", "https://img.icons8.com/color/48/gears.png", "T1_Deals_Form", "加工受託", "", 2],
      ["B-03", "✨ 新品機械を販売する", "https://img.icons8.com/color/48/manufacturing.png", "T1_Deals_Form", "新品機械", "", 3],
      ["B-04", "🔄 中古機械を売買する", "https://img.icons8.com/color/48/recycle.png", "T1_Deals_Form", "中古機械", "", 4],
      ["B-05", "🩺 機械修理を手配する", "https://img.icons8.com/color/48/stethoscope.png", "T1_Deals_Form", "修理", "", 5],
      ["B-06", "⚙️ 工具メンテを手配する", "https://img.icons8.com/color/48/maintenance.png", "T1_Deals_Form", "工具メンテナンス", "", 6],
      ["B-07", "📄 見積書を作成する", "https://img.icons8.com/color/48/document--v1.png", "T2_Papers_Form", "", "", 7]
    ];
    launcherSheet.getRange(2, 1, initialLaunchers.length, 7).setValues(initialLaunchers);
  }

  Logger.log("✨ データベースの構築（v4.0 最新版）が完了しました。");
}
