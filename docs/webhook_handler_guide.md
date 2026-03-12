# Webhook & 自動フォルダ作成 (AppSheet → GAS連携)

AppSheetで「1. 活動ログ」が新規作成された瞬間、AppSheetからGASへ指令（Webhook）を飛ばし、Googleドライブ内に自動で案件専用のフォルダを生成するためのスクリプトです。

これを先に作成した `ultimate_gas_modules.md` の一連のGASモジュール群に追加して保存し、「ウェブアプリ（Web App）としてデプロイ」する必要があります。

---

### 追加コード：`webhook_handler.gs`

```javascript
/**
 * webhook_handler.gs: AppSheetからの指令を受け取る
 */

// POSTリクエストの入口（AppSheetのWebhookアクションからここが叩かれる）
function doPost(e) {
  try {
    // 1. AppSheetから送られてきたJSONデータを解析
    const payload = JSON.parse(e.postData.contents);
    const action = payload.action;
    
    // 2. アクションに応じた処理の分岐
    if (action === "CREATE_PROJECT_FOLDER") {
      return handleCreateFolder(payload);
    }
    
    return ContentService.createTextOutput("Success (No action taken)");

  } catch (error) {
    console.error(error);
    return ContentService.createTextOutput("Error: " + error.message);
  }
}

/**
 * フォルダを自動生成し、URLをシートに書き戻す
 */
function handleCreateFolder(payload) {
  const logId = payload.logId;
  const dealName = payload.dealName; // 件名_概要
  
  // 1. 親フォルダを取得 (config.gs の CONFIG.PARENT_FOLDER_ID を使用)
  const parentFolder = DriveApp.getFolderById(CONFIG.PARENT_FOLDER_ID);
  
  // 2. フォルダ名の決定（例: "L-240225-xyz_工具見積作成"）
  const folderName = `${logId}_${dealName}`;
  
  // 3. ドライブ上に新規フォルダを作成
  const newFolder = parentFolder.createFolder(folderName);
  const folderUrl = newFolder.getUrl();
  
  // 4. (必要なら) シート検索してURLを自動記述する処理をここに追加
  // ※ AppSheet側でファイルアップロードカラムを設定すれば、実はフォルダURLを手動でシートに持たせなくても
  //   AppSheetが自動で「(テーブル名)_Files」配下に写真を保存してくれます。
  //   この機能は「案件ごとに全ての書類や図面を1箇所にまとめたい」場合の専用フォルダ生成に使います。

  return ContentService.createTextOutput("Folder created: " + folderUrl);
}
```

---

## 【AppSheet側の設定手順】 (Bot Automation)

GAS側で上記の `doPost` をデプロイし、ウェブアプリの「URL」を発行したら、AppSheetエディタの `Automation（ボットマーク）` で以下の設定を行います。

1. **New Bot** > Create a new bot
2. **Event**: 
    - Event Type: `Data Change`
    - Tables: `1. 活動ログ (DealsLogs)`
    - Condition: `Adds only` (新規追加時のみ)
3. **Step** > **Run a task**:
    - Task type: `Call a webhook`
    - Preset: `Custom`
    - Url: `(GASで発行したURLを貼り付け)`
    - HTTP Verb: `POST`
    - HTTP Content Type: `JSON`
    - Body:
    ```json
    {
      "action": "CREATE_PROJECT_FOLDER",
      "logId": "<<[ログID]>>",
      "dealName": "<<[件名_概要]>>"
    }
    ```

これにより、AppSheetで活動ログをポチッと登録すると、裏で一瞬にしてGoogleドライブに専用フォルダが作られるようになります！
