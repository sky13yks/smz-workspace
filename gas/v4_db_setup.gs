/**
 * ============================================================================
 * 案件管理システム V5.0 - スプレッドシート DB構築スクリプト (v4_db_setup.gs)
 * ============================================================================
 * 設計書: docs/v5_design_revised.md
 *
 * 【使い方】
 * 1. 新規スプレッドシートを作成
 * 2. 拡張機能 > Apps Script を開く
 * 3. このコードを貼り付けて setupV4Database 関数を実行
 *
 * ⚠️ 既存データがある場合は各シートをクリアします。
 *    運用中のスプレッドシートには実行しないでください。
 */

function setupV4Database() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const tables = [

    // ── マスタ系 ──────────────────────────────────────────────────
    {
      name: "M1_Companies",
      desc: "会社マスタ（顧客・仕入先・修理業者 共用）",
      cols: ["会社ID", "会社名", "会社名カナ", "取引区分", "郵便番号", "住所",
             "電話番号", "FAX番号", "締日", "支払条件", "掛け率", "備考"]
      // 掛け率: メンテナンス価格表への乗率（例: 1.3 = 仕入価格の1.3倍で販売）
    },
    {
      name: "M2_Contacts",
      desc: "担当者マスタ（M1に所属する人）",
      cols: ["担当者ID", "会社ID", "氏名", "区分", "部署", "役職",
             "メール", "電話番号", "名刺画像", "電子印影URL", "退職/異動フラグ"]
    },
    {
      // 工具メンテナンス価格表（外径×厚みのマトリクス）
      // 行 = サイズ区分（外径_上限×厚み_上限の組み合わせ）
      // 各価格列は「仕入れ価格（弊社コスト）」を記載
      // 販売価格 = 仕入れ価格 × M1_Companies.掛け率
      name: "M3_ToolPricing",
      desc: "工具メンテ価格表（外径×厚みのサイズ区分ごとの仕入れ単価）",
      cols: ["価格ID", "外径_上限mm", "厚み_上限mm",
             "研磨_0.5mm", "研磨_1.0mm", "研磨_1.5mm", "研磨_2.0mm",
             "脱膜処理", "再コーティング", "DB処理",
             "備考"]
      // ※ 記載サイズ外の工具は「都度見積」となるため本表に含まない
    },
    {
      name: "M4_Settings",
      desc: "システム設定マスタ（定数・閾値）",
      cols: ["設定キー", "設定値", "説明"]
    },
    {
      name: "M6_Tools",
      desc: "工具マスタ（よく扱うオーダーメイド工具の雛形。カタログ品全登録は不要）",
      cols: ["工具ID", "メーカー会社ID", "工具名称", "型式・品番", "工具区分",
             "材質", "コーティング", "外径", "全長", "仕様詳細", "標準単価", "備考", "カタログURL"]
    },

    // ── 資産系 ────────────────────────────────────────────────────
    {
      name: "A1_Assets",
      desc: "個体管理（工具・中古機械・新品機械の現物追跡）",
      cols: ["個体ID", "個体名称", "個体区分", "所有会社ID", "メーカー会社ID",
             "諸元ID", "初回案件ID",
             "工具図面URL", "外径", "厚み", "内径", "材質",
             "累計研磨回数", "最終メンテ日",
             "型式", "年式", "仕様書URL",
             "仕入値", "販売希望価格_dealer", "販売希望価格_user", "在庫ステータス",
             "備考"]
    },
    {
      name: "A2_WorkSpecs",
      desc: "ワーク諸元（何を削るかの技術仕様）",
      cols: ["諸元ID", "ワーク名称", "加工区分", "モジュール/ピッチ", "圧力角",
             "ねじれ方向", "条数", "ワーク図面URL", "数量", "備考"]
    },

    // ── トランザクション系 ────────────────────────────────────────
    {
      name: "T1_Deals",
      desc: "案件管理ヘッダ（全業務カテゴリのハブ）",
      cols: ["案件ID", "案件名", "業務カテゴリ", "修理区分", "中古機械小分類",
             "ステータス", "顧客会社ID", "仕入先会社ID",
             "自社担当者ID", "事務担当者ID", "親案件ID",
             "失注フラグ", "失注理由", "共同購入フラグ", "共同購入先会社ID",
             "発生日", "希望納期", "ステータス更新日",
             "ドライブフォルダURL", "判断メモ", "備考"]
    },
    {
      name: "T1D_DealItems",
      desc: "案件明細（1案件に複数品目がある場合）",
      cols: ["明細ID", "案件ID", "品名・内容", "諸元ID", "個体ID", "数量", "備考"]
    },
    {
      name: "T2_Papers",
      desc: "帳票管理（見積書・発注書・作業報告書・納品書・請求書 統合）",
      cols: ["帳票ID", "案件ID", "種別", "元帳票ID", "相手先会社ID",
             "発行日", "有効期限", "合計金額",
             "前払フラグ", "前払割合", "前払金額",
             "承認図面フラグ", "入金確認", "入金日", "複製フラグ", "PDF_URL", "備考"]
    },
    {
      name: "T2D_PaperLines",
      desc: "帳票明細行",
      cols: ["明細ID", "帳票ID", "案件明細ID", "項目名", "数量", "単位", "単価", "金額", "備考"]
    },
    {
      name: "T4_QuoteRequests",
      desc: "仕入見積依頼（形状バリアント単位。1案件に複数行可）",
      cols: ["依頼ID", "案件ID", "依頼種別", "形状バリアント",
             "仕様概要", "依頼日", "回答期限", "採用フラグ", "採用理由メモ", "備考"]
    },
    {
      name: "T4D_QuoteResponses",
      desc: "仕入見積回答（T4_QuoteRequests 1件に対して複数メーカーの回答）",
      cols: ["回答ID", "依頼ID", "仕入先会社ID", "回答日",
             "回答金額", "回答納期", "採用フラグ", "採用_非採用理由", "回答書PDF_URL", "備考"]
    },
    {
      name: "T5_Files",
      desc: "書類管理（案件に紐づく全ファイルのURLリンク集）",
      cols: ["資料ID", "案件ID", "個体ID", "ファイル名",
             "カテゴリ", "サフィックス", "ファイルURL", "登録日", "備考"]
    },
    {
      name: "T6_WorkLogs",
      desc: "作業履歴（工具メンテ・修理作業の実績記録）",
      cols: ["履歴ID", "案件ID", "個体ID", "作業区分", "作業日",
             "研磨量mm", "コーティング膜種", "DB処理有無", "除膜処理有無", "算出価格",
             "作業者区分", "作業業者会社ID",
             "同行費用有無", "作業写真", "作業メモ"]
    },
    {
      name: "T7_RepairExpenses",
      desc: "修理・出張費用明細（高速代・ガソリン代・同行日当・部品代・重量輸送費 等）",
      cols: ["費用ID", "案件ID", "費用種別", "発生日",
             "金額", "数量", "小計", "支払先", "領収書URL", "備考"]
    },

    // ── システム系 ────────────────────────────────────────────────
    {
      name: "L1_Launcher",
      desc: "AppSheet ランチャー（業務カテゴリ別ボタン）",
      cols: ["ボタンID", "ボタン名", "アイコン画像URL", "遷移先ビュー名",
             "業務カテゴリセット値", "表示順"]
    }
  ];

  // 各シートを作成または初期化
  tables.forEach(function(table) {
    var sheet = ss.getSheetByName(table.name);
    if (!sheet) {
      sheet = ss.insertSheet(table.name);
      Logger.log("シート「" + table.name + "」を新規作成しました。");
    } else {
      sheet.clear();
      Logger.log("シート「" + table.name + "」を上書きクリアしました。");
    }

    sheet.getRange(1, 1, 1, table.cols.length).setValues([table.cols]);

    var headerRange = sheet.getRange(1, 1, 1, table.cols.length);
    headerRange.setBackground("#4c1130")
               .setFontColor("#ffffff")
               .setFontWeight("bold")
               .setHorizontalAlignment("center");

    sheet.setFrozenRows(1);
    sheet.autoResizeColumns(1, table.cols.length);
  });

  // 初期不要シート削除
  var defaultSheet = ss.getSheetByName("シート1");
  if (defaultSheet && ss.getSheets().length > 1) {
    ss.deleteSheet(defaultSheet);
  }

  // ── 初期データ: M3_ToolPricing（価格表サンプル）────────────────
  var pricingSheet = ss.getSheetByName("M3_ToolPricing");
  if (pricingSheet && pricingSheet.getLastRow() === 1) {
    // 実際の価格表PDFの値に合わせて書き換えてください
    // 各価格は「仕入れ価格（弊社コスト）」です。販売価格 = 仕入価格 × M1.掛け率
    var samplePricing = [
      ["MP-01",  50,  10, 2000, 3500, 5000, 6000,  800,  7000, 4000, "外径50mm以下、厚み10mm以下"],
      ["MP-02",  50,  20, 2500, 4000, 5500, 6500,  900,  8000, 4500, "外径50mm以下、厚み20mm以下"],
      ["MP-03",  50,  30, 3000, 4500, 6000, 7000, 1000,  9000, 5000, "外径50mm以下、厚み30mm以下"],
      ["MP-04", 100,  10, 3000, 5000, 7000, 9000, 1200,  9000, 5000, "外径100mm以下、厚み10mm以下"],
      ["MP-05", 100,  20, 3500, 5500, 7500, 9500, 1400, 10000, 5500, "外径100mm以下、厚み20mm以下"],
      ["MP-06", 100,  40, 4000, 6000, 8000,10000, 1600, 11000, 6000, "外径100mm以下、厚み40mm以下"],
      ["MP-07", 150,  20, 4500, 7000, 9500,12000, 1800, 12000, 6500, "外径150mm以下、厚み20mm以下"],
      ["MP-08", 150,  50, 5000, 7500,10000,13000, 2000, 13000, 7000, "外径150mm以下、厚み50mm以下"],
      ["MP-99",   0,   0,    0,    0,     0,    0,    0,     0,    0, "サイズ外 → 都度見積"]
    ];
    pricingSheet.getRange(2, 1, samplePricing.length, 11).setValues(samplePricing);
    Logger.log("M3_ToolPricing: サンプル価格表を投入しました。実際の価格表PDFに合わせて数値を修正してください。");
  }

  // ── 初期データ: M4_Settings ──────────────────────────────────
  var settingsSheet = ss.getSheetByName("M4_Settings");
  if (settingsSheet && settingsSheet.getLastRow() === 1) {
    var initialSettings = [
      ["同行日当_平日",        "65000",  "自社スタッフ同行修理 1日あたり日当（平日）"],
      ["同行日当_休日",        "80000",  "自社スタッフ同行修理 1日あたり日当（休日・祝日）"],
      ["利益率警告閾値",       "15",     "粗利率がこれを下回るとアラート（単位: %）"],
      ["研磨回数アラート閾値",  "5",      "累計研磨回数がこれを超えると新品提案リマインド"],
      ["消費税率",             "0.10",   "現行消費税率（2026年現在 10%）"],
      ["見積有効期限_日数",    "30",     "販売見積書のデフォルト有効期限（発行日からの日数）"],
      ["MATRIX前払率_1次",    "0.30",   "Matrix台湾 発注時前払い割合（30%）"],
      ["MATRIX前払率_2次",    "0.70",   "Matrix台湾 出荷時支払い割合（70%）"],
      ["価格表PDF_URL",        "",       "工具メンテ価格表のPDF保存URL（Driveにアップ後に入力）"]
    ];
    settingsSheet.getRange(2, 1, initialSettings.length, 3).setValues(initialSettings);
  }

  // ── 初期データ: L1_Launcher ──────────────────────────────────
  var launcherSheet = ss.getSheetByName("L1_Launcher");
  if (launcherSheet && launcherSheet.getLastRow() === 1) {
    var initialLaunchers = [
      ["B-01", "🔧 オーダーメイド工具", "https://img.icons8.com/color/48/drill.png",        "T1_Deals_Form", "オーダーメイド工具", 1],
      ["B-02", "📦 カタログ品工具",     "https://img.icons8.com/color/48/toolbox.png",       "T1_Deals_Form", "カタログ品工具",     2],
      ["B-03", "🔩 工具メンテナンス",   "https://img.icons8.com/color/48/maintenance.png",   "T1_Deals_Form", "工具メンテナンス",   3],
      ["B-04", "🏭 加工受託",           "https://img.icons8.com/color/48/gears.png",          "T1_Deals_Form", "加工受託",           4],
      ["B-05", "🩺 機械修理",           "https://img.icons8.com/color/48/stethoscope.png",   "T1_Deals_Form", "機械修理",           5],
      ["B-06", "🔄 中古機械",           "https://img.icons8.com/color/48/recycle.png",        "T1_Deals_Form", "中古機械",           6],
      ["B-07", "✨ 新品機械販売",       "https://img.icons8.com/color/48/manufacturing.png", "T1_Deals_Form", "新品機械販売",       7]
    ];
    launcherSheet.getRange(2, 1, initialLaunchers.length, 6).setValues(initialLaunchers);
  }

  Logger.log("✨ データベース v5.0 の構築が完了しました。シート数: " + tables.length);
  Logger.log("⚠️  M3_ToolPricingのサンプル価格は仮の値です。実際の価格表PDFに合わせて修正してください。");
}
