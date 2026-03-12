
/**
 * ============================================================================
 * 案件管理システム V1系 - レガシーコード (Code.gs)
 * ============================================================================
 * ⚠️ このファイルの doPost / replaceList はv1時代の旧実装です。
 *    現行エントリポイントは v4_gas_core.gs の doPost() です。
 *    testCreateDocument() はGASエディタからの手動テスト用として残しています。
 * ============================================================================
 */

// ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★
// ★ 初期設定：以下のIDを実際のGoogleドライブのものに書き換えてください ★
// ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

// 見積書テンプレートとして使用するGoogleドキュメントのID
const TEMPLATE_ID = "YOUR_TEMPLATE_DOCUMENT_ID"; 

// 作成した見積書を保存するGoogleドライブのフォルダID
const DESTINATION_FOLDER_ID = "YOUR_DESTINATION_FOLDER_ID";

// ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

/**
 * [レガシー] AppSheetからPOSTリクエストを受け取るメイン関数
 * ⚠️ 現行システムでは使用しません。v4_gas_core.gs の doPost() を使用してください。
 */
function doPost_legacy_v1(e) {
  try {
    // POSTされたJSONデータをパース
    const requestData = JSON.parse(e.postData.contents);
    
    // テンプレートドキュメントを取得
    const templateDoc = DocumentApp.openById(TEMPLATE_ID);
    const templateName = templateDoc.getName();
    
    // 保存先フォルダを取得
    const destinationFolder = DriveApp.getFolderById(DESTINATION_FOLDER_ID);
    
    // 新しいドキュメントを作成
    const newDocName = `見積書_${requestData.顧客名}_${requestData.件名}`;
    const newFile = DriveApp.getFileById(TEMPLATE_ID).makeCopy(newDocName, destinationFolder);
    const newDoc = DocumentApp.openById(newFile.getId());
    const body = newDoc.getBody();

    // ヘッダー情報の置換
    body.replaceText("<<顧客名>>", requestData.顧客名 || "");
    body.replaceText("<<発行日>>", requestData.発行日 || "");
    body.replaceText("<<見積ID>>", requestData.見積ID || "");
    body.replaceText("<<件名>>", requestData.件名 || "");
    body.replaceText("<<有効期限>>", requestData.有効期限 || "");
    body.replaceText("<<全体備考>>", requestData.全体備考 || "");
    body.replaceText("<<小計>>", requestData.小計 || "0");
    body.replaceText("<<消費税>>", requestData.消費税 || "0");
    body.replaceText("<<合計金額>>", requestData.合計金額 || "0");

    // 明細情報の処理
    const details = requestData.関連する見積明細 || [];
    replaceList(body, details);

    // ドキュメントを保存して閉じる
    newDoc.saveAndClose();
    
    // 成功レスポンスを返す
    return ContentService.createTextOutput(JSON.stringify({ 
      status: "success", 
      message: "見積書を作成しました。",
      documentUrl: newDoc.getUrl() 
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    // エラーレスポンスを返す
    return ContentService.createTextOutput(JSON.stringify({ 
      status: "error", 
      message: error.message,
      stack: error.stack
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 明細リストを処理する関数
 */
function replaceList(body, details) {
  const startTag = "<<Start: [関連する見積明細]>>";
  const endTag = "<<End>>";

  const listTemplateRange = body.findText(startTag + ".*" + endTag, null);
  if (!listTemplateRange) {
    // テンプレートにStart/Endタグが見つからない場合は何もしない
    return;
  }

  const listTemplateElement = listTemplateRange.getElement();
  const parent = listTemplateElement.getParent();
  const listTemplateString = listTemplateElement.asText().getText().slice(startTag.length, -endTag.length);
  
  // 元のテンプレートを削除
  listTemplateElement.asText().setText("");

  // 明細データを逆順に挿入（挿入位置がずれないようにするため）
  details.reverse().forEach(detail => {
    let newListItemText = listTemplateString;
    newListItemText = newListItemText.replace("<<分類>>", detail.分類 || "");
    newListItemText = newListItemText.replace("<<品番>>", detail.品番 || "");
    newListItemText = newListItemText.replace("<<品名>>", detail.品名 || "");
    newListItemText = newListItemText.replace("<<仕様詳細>>", detail.仕様詳細 || "");
    newListItemText = newListItemText.replace("<<数量>>", detail.数量 || "0");
    newListItemText = newListItemText.replace("<<単価>>", detail.単価 || "0");
    newListItemText = newListItemText.replace("<<金額>>", detail.金額 || "0");
    
    parent.insertParagraph(parent.getChildIndex(listTemplateElement) + 1, newListItemText);
  });
}

/**
 * テスト用の関数
 * Google Apps Scriptエディタから直接実行して動作確認ができます。
 */
function testCreateDocument() {
  const mockEvent = {
    postData: {
      contents: JSON.stringify({
        "顧客名": "テスト株式会社",
        "件名": "新規お見積りの件",
        "発行日": "2025/07/20",
        "有効期限": "1ヶ月",
        "見積ID": "QT-2025-001",
        "全体備考": "別途送料がかかります。",
        "小計": "66,000",
        "消費税": "6,600",
        "合計金額": "72,600",
        "関連する見積明細": [
          {
            "分類": "キーシーターカッター",
            "品番": "No.3-10 JS9 R0.3",
            "品名": "SKH55 キーシーターカッター(新規TiCNコーティング)",
            "仕様詳細": "45×18×13",
            "数量": "1",
            "単価": "22,000",
            "金額": "22,000"
          },
          {
            "分類": "新作ホブ",
            "品番": "No.A-20 DP20 PA20",
            "品名": "超硬ホブ (新規ALTコーティング)",
            "仕様詳細": "φ50xφ22x40L",
            "数量": "2",
            "単価": "22,000",
            "金額": "44,000"
          }
        ]
      })
    }
  };
  
  // doPostをテストデータで実行
  doPost(mockEvent);
}
