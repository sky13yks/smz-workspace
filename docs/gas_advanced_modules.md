# マージンチェックとAppSheetWebhook連携設定

モジュール分割したGASに、案件の利益率を自動判定する機能と、AppSheetから処理を呼び出すための「Webhook（Web Endpoint）」を追加します。

### コード5：`dealManager.gs` (バリデーションと計算)

```javascript
/** ==============================================
 * dealManager.gs: 案件ごとのビジネスロジック
 * ============================================== */

const DealManager = {
  /**
   * 利益率（マージン）を計算し、閾値を下回る場合は警告メッセージを返す
   * @param {number} cost 仕入（原価）
   * @param {number} price 販売価格（売上）
   * @return {Object} { margin: number, warning: string }
   */
  checkMargin: function(cost, price) {
    if (!price || price <= 0) return { margin: 0, warning: "" };
    
    // (売上 - 原価) / 売上 * 100 
    const margin = ((price - cost) / price) * 100;
    let warning = "";
    
    // config.gs で設定した閾値 (例: 15%) を下回るかチェック
    if (margin < CONFIG.MARGIN_WARNING_PERCENT) {
      warning = `【警告】利益率が基準（${CONFIG.MARGIN_WARNING_PERCENT}%）を下回っています。承認者の確認が必要です。`;
    }
    
    return {
      margin: Math.round(margin * 10) / 10, // 小数第1位で丸める
      warning: warning
    };
  }
};
```

---

### コード6：`doPost.gs` (AppSheet Webhook受け口)
AppSheetから**「Bot」を使ってイベント駆動でGASを動かす**ための推奨される受け口（Endpoint）です。これを使うことで、トリガー不要で確実に関数を呼び出せます。

```javascript
/** ==============================================
 * doPost.gs: AppSheet Webhookからの受信口
 * ============================================== */

/**
 * 外部（AppSheet等）からHTTP POSTリクエストを受けた時に動く関数
 */
function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const action = params.action; // AppSheet側から送ってくる処理名
    
    if (action === "CREATE_PROJECT_FOLDER") {
      // ドライブフォルダを新規作成し、URLを返すロジック（後述のassetManager等へ渡す）
      return createJsonResponse({ status: "success", message: "Folder Created" });
    }
    
    // その他のアクション判定...
    
  } catch (err) {
    return createJsonResponse({ status: "error", message: err.toString() }, 400);
  }
}

/**
 * 呼び出し元（AppSheet）にJSON形式で結果を返すヘルパー
 */
function createJsonResponse(data, statusCode = 200) {
  const output = ContentService.createTextOutput(JSON.stringify(data));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}
```

## 次のステップへの準備
これらのモジュールを作成した後は、**スプレッドシート上のデータを一旦空にし、初期構築スクリプト(`initializeAdvancedDatabase`)を実行して「7つのテーブル」を作り直します。** その後、AppSheet側でその7テーブルを再読み込みし、親子関係の構築を進めていきます。
