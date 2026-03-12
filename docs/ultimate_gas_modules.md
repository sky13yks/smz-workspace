# 究極版GASモジュール構成 (15テーブル・高度価格計算対応)

スプレッドシートを15テーブルで構築した後、それらを制御するための「機能分割（モジュール化）」されたGASコード一式です。各ファイルをApps Scriptエディタで作成してください。

---

### コード1：`config.gs` (全体設定)
システムの全ての定数をここで管理します。

```javascript
/**
 * config.gs: システム設定
 */
const CONFIG = {
  // Googleドライブの親フォルダID
  PARENT_FOLDER_ID: "ここにあなたの親フォルダIDを記入",
  
  // 利益率（マージン）の警告閾値 (%)
  MARGIN_THRESHOLD: 15.0,

  // シート名の定義（コード内でシート名を直接書かず、これを使います）
  SHEETS: {
    LOGS: "1. 活動ログ (DealsLogs)",
    MACHINE_MAINT: "2. 機械メンテ (MachineMaint)",
    TOOL_MAINT: "4. 工具メンテ (ToolMaint)",
    DOC_ESTIMATE: "5. 見積_注文書 (EstimateOrders)",
    DOC_ITEMS: "6. 書類明細 (LineItems)",
    MASTER_TOOLS: "M5. 工具マスタ (Tools)",
    PRICING_MASTER: "M7. 工具価格マスタ (ToolPricing)"
  }
};
```

---

### コード2：`idGenerator.gs` (自動採番)
各テーブルのIDルールを司ります。

```javascript
/**
 * idGenerator.gs: 各種IDの自動生成
 */
const IdGenerator = {
  // 案件ログ用: YYMMDD-LOG-XXXX
  generateLogId: function() {
    const now = new Date();
    const prefix = Utilities.formatDate(now, "Asia/Tokyo", "yyMMdd") + "-LOG-";
    return prefix + Math.random().toString(36).substring(2, 6).toUpperCase();
  },
  
  // 見積・注文書用: DOC-YYMM-XXXX
  generateDocId: function() {
    const now = new Date();
    const prefix = "DOC-" + Utilities.formatDate(now, "Asia/Tokyo", "yyyyMM") + "-";
    return prefix + Math.random().toString(36).substring(2, 6).toUpperCase();
  }
};
```

---

### コード3：`pricingLogic.gs` (研磨・コーティング価格算出)
今回のご要望の目玉となる「0.5mm刻み」と「コーティング種別」の計算ロジックです。

```javascript
/**
 * pricingLogic.gs: 高度な価格計算
 */
const PricingLogic = {
  /**
   * 研磨料金の算出 (基本0.5mm + 0.5mm刻み加算)
   * @param {number} diameter 外径
   * @param {number} thickness 厚み
   * @param {number} amount 研磨量(mm)
   */
  calculateGrindingPrice: function(diameter, thickness, amount) {
    // 1. マスタ(M7)から該当サイズ(外径/厚み)の基本価格と加算単価を検索（疑似的な検索処理）
    // TODO: 実際にはマスターシートを検索するように拡張
    const basePrice = 2000;  // 仮: マスタから引用
    const unitPrice = 500;   // 仮: マスタから引用 (0.5mm超えごとの加算額)
    
    if (amount <= 0.5) return basePrice;
    
    // 0.5mmを超える分を0.5で割り、切り上げ (例: 0.6mm -> 1ステップ)
    const extraSteps = Math.ceil((amount - 0.5) / 0.5);
    return basePrice + (extraSteps * unitPrice);
  },

  /**
   * コーティング料金の算出
   */
  calculateCoatingPrice: function(type, diameter, thickness) {
    // TiCNはTiNと同価格として扱うマッピング
    const lookupType = (type === "TiCN") ? "TiN" : type;
    
    // TODO: ここで M7. 工具価格マスタ を検索
    return 3000; // 仮
  }
};
```

---

### コード4：`trigger.gs` (AppSheet連携)
AppSheetからデータが飛んできた時の「司令塔」です。

```javascript
/**
 * trigger.gs: イベント制御
 */
function onSheetUpdate(e) {
  const sheet = e.source.getActiveSheet();
  const sheetName = sheet.getName();
  const row = e.range.getRow();
  if (row <= 1) return;

  // 活動ログが追加された時の処理
  if (sheetName === CONFIG.SHEETS.LOGS) {
    const range = sheet.getRange(row, 1, 1, 1); // ログID列(A列)
    if (!range.getValue()) {
      range.setValue(IdGenerator.generateLogId());
      // TODO: ここで案件別のドライブフォルダ自動作成を呼び出す
    }
  }
}
```

これらのコードは、お客様自身が**スプレッドシートの「工具価格マスター」などを手動で整え終えた後**に、そのシート構成に合わせて細部（どの列が外径か、など）をチューニングすることで真価を発揮します。
まずはこの「土台」をGASエディタに入れておき、準備が整い次第アクションの設定に入りましょう！
