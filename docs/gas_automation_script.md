# 自動化機能: 案件用ドライブフォルダ＆ID自動採番（AppSheet連携）

AppSheetから「新規の案件」が作成された瞬間に、連動してGoogleドライブ上に自動でその案件専用のフォルダを作り、スプレッドシート（AppSheet）側にフォルダのURLと自動採番した案件IDを書き戻すスクリプトです。

## 【手順1】Googleドライブ側の準備
1. Googleドライブを開き、すべての案件を入れる「親フォルダ（例：案件一式フォルダ）」を作成します。
2. 作成した親フォルダを開き、ブラウザのURLから **フォルダID** をコピーして控えます。
   ※URLが `https://drive.google.com/drive/folders/1aBcD2eFgH3iJ...` なら、`1aBcD2eFgH3iJ...` の部分がフォルダIDです。

## 【手順2】GASへの自動化スクリプト追加
1. スプレッドシートの「拡張機能」 ＞ 「Apps Script」を開きます。
2. `コード.gs` ファイルの末尾（以前書いた `initializeCoreDatabase` 関数の下）に、以下のコードを追記します。
3. コード内の `PARENT_FOLDER_ID` を、手順1で控えた**あなたのフォルダID**に書き換えてください。

```javascript
/* =======================================================================
 * AppSheet 新規追加時のバックグラウンド自動処理（フォルダ作成＆ID採番）
 * ======================================================================= */

// ★ここに作成したドライブの親フォルダID（英数字の羅列）を貼り付けてください
const PARENT_FOLDER_ID = "ここに親フォルダのIDを貼り付けます";

/**
 * AppSheetからスプレッドシートに行が追加（変更）された時に自動で動く関数
 * @param {Object} e - 編集イベントオブジェクト
 */
function onEditTrigger(e) {
  const sheet = e.source.getActiveSheet();
  
  // 「案件管理DB」シートの編集でない場合は何もしない
  if (sheet.getName() !== "案件管理DB") return;
  
  // 見出し行の編集は何もしない
  const row = e.range.getRow();
  if (row <= 1) return;

  // 編集された行のデータをごっそり取得
  const lastCol = sheet.getLastColumn();
  const rowDataRange = sheet.getRange(row, 1, 1, lastCol);
  const rowData = rowDataRange.getValues()[0];
  
  const currentProjectId = rowData[0]; // A列: 案件ID
  const projectName = rowData[1];      // B列: 案件名
  const folderUrl = rowData[8];        // I列: ドライブフォルダURL
  
  let isUpdated = false;

  // -------------------------------------------------------------------
  // 1. 案件IDの自動採番（空の場合のみ）
  // -------------------------------------------------------------------
  if (!currentProjectId || String(currentProjectId).trim() === "") {
    // 例: PRJ-202403-0001 のようなIDを生成
    const now = new Date();
    const yyyymm = Utilities.formatDate(now, "Asia/Tokyo", "yyyyMM");
    // 行番号を使って簡易的な連番とする（本格的な連番管理は別シートで行う場合もあり）
    const sequentialNum = ("000" + (row - 1)).slice(-4); 
    const newProjectId = "PRJ-" + yyyymm + "-" + sequentialNum;
    
    sheet.getRange(row, 1).setValue(newProjectId); // A列に書き込み
    rowData[0] = newProjectId; // 変数も更新
    isUpdated = true;
  }

  // -------------------------------------------------------------------
  // 2. Googleドライブの自動フォルダ作成（URLが空の場合のみ）
  // -------------------------------------------------------------------
  if (!folderUrl || String(folderUrl).trim() === "") {
    // フォルダ名: 「案件ID_案件名」にする
    const newFolderName = rowData[0] + "_" + (projectName ? projectName : "無題の案件");
    
    try {
      const parentFolder = DriveApp.getFolderById(PARENT_FOLDER_ID);
      const newFolder = parentFolder.createFolder(newFolderName);
      const newFolderUrl = newFolder.getUrl();
      
      // I列（ドライブフォルダURL）に作成したフォルダのリンクを書き込み
      sheet.getRange(row, 9).setValue(newFolderUrl);
      isUpdated = true;
      
    } catch (e) {
      Logger.log("フォルダ作成エラー: " + e.message);
    }
  }
}
```

## 【手順3】GASの「トリガー（自動起動設定）」を登録
このスクリプトは、「スプレッドシートに変更があったとき（AppSheetからデータが送信されたとき）」に自動で動かす必要があります。

1. Apps Script画面の左側メニューから、時計マークのアイコン（**トリガー**）をクリックします。
2. 画面右下の青いボタン **「トリガーを追加」** をクリックします。
3. 以下の通り設定して「保存」を押します。
   * **実行する関数を選択**: `onEditTrigger`
   * **実行するデプロイを選択**: `Head`
   * **イベントのソースを選択**: `スプレッドシートから`
   * **イベントの種類を選択**: `変更時` （※「編集時」ではなく「変更時」を選んでください）
4. （初回のみ）Googleのアクセス承認画面が出ますので、ご自身のアカウントで許可（Allow）してください。

### 【テスト方法】
これで自動化の設定は完了です！
AppSheet（またはスプレッドシートに直接）で、「案件名」だけを入力して保存してみてください。
数秒待つと、同じ行の「案件ID」と「ドライブフォルダURL」に自動で値が書き込まれます。
