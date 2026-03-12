/**
 * ============================================================================
 * 案件管理システム V4.0 - GAS Core モジュール (v4_gas_core.gs)
 * ============================================================================
 * 
 * AppSheetからのWebhook（JSON）を受け取り、各種バックエンド処理へルーティングします。
 * 主な機能：
 *  1. Webhookルーティング (doPost)
 *  2. Google Drive 案件フォルダの自動生成 (createDealFolder)
 */

// 定数定義 (環境に合わせて変更してください)
const ROOT_FOLDER_ID = "1vC42vwxAH-mwscr3F_kbPLi3E9ZB_GhK"; 
// ※ Google Driveでフォルダを開いたときのURL末尾にある英数字文字列

/**
 * Webhookのエンドポイント (AppSheetからのPOSTリクエストを受け取る)
 */
function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents);
    const actionType = payload.actionType;
    let resultMessage = "Unknown actionType";

    if (actionType === "CREATE_FOLDER") {
      resultMessage = createDealFolder(payload.dealId, payload.dealName, payload.customerId);
    } else if (actionType === "DEEP_COPY_PAPERS") {
      // v4_gas_papers.gs の関数を呼び出し
      resultMessage = copyPaperAndLines(payload.sourcePaperId, payload.targetType);
    } else if (actionType === "GENERATE_PDF") {
      // v4_gas_papers.gs の関数を呼び出し
      resultMessage = generatePaperPdf(payload.paperId);
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "success", message: resultMessage }))
                         .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    console.error(error);
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: error.message }))
                         .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * 新規案件フォルダを作成し、T1_DealsシートにフォルダURLを書き込む
 * @param {string} dealId - 案件ID
 * @param {string} dealName - 案件名
 * @param {string} customerId - 顧客会社ID (フォルダの階層分けなどに利用)
 */
function createDealFolder(dealId, dealName, customerId) {
  // 1. ルートフォルダを取得
  const rootFolder = DriveApp.getFolderById(ROOT_FOLDER_ID);
  
  // 2. 顧客名を取得（T1シートに会社名が入っていない前提のため、M1シートから引く）
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let companyName = "その他";
  if (customerId) {
    const m1Sheet = ss.getSheetByName("M1_Companies");
    const m1Data = m1Sheet.getDataRange().getValues();
    const companyRow = m1Data.find(row => row[0] === customerId); // 会社IDは0列目
    if (companyRow) companyName = companyRow[1]; // 会社名は1列目
  }

  // 3. 顧客ごとの親フォルダを探す、無ければ作る
  let companyFolder;
  const companyFolderIter = rootFolder.getFoldersByName(companyName);
  if (companyFolderIter.hasNext()) {
    companyFolder = companyFolderIter.next();
  } else {
    companyFolder = rootFolder.createFolder(companyName);
  }

  // 4. 案件フォルダを作成
  const folderName = `[${dealId}] ${dealName}`;
  const dealFolder = companyFolder.createFolder(folderName);
  const folderUrl = dealFolder.getUrl();

  // 5. T1_Deals シートの該当案件にURLを書き戻す
  const t1Sheet = ss.getSheetByName("T1_Deals");
  const t1Data = t1Sheet.getDataRange().getValues();
  const headers = t1Data[0];
  const colId = headers.indexOf("案件ID");
  const colUrl = headers.indexOf("ドライブフォルダURL");

  for (let i = 1; i < t1Data.length; i++) {
    if (t1Data[i][colId] === dealId) {
      t1Sheet.getRange(i + 1, colUrl + 1).setValue(folderUrl);
      break;
    }
  }

  return `Folder created successfully: ${folderUrl}`;
}

/**
 * ============================================================
 * 【テスト用】createDealFolder の動作確認
 * GASエディタで直接この関数を実行してください。
 * 実行後、ROOT_FOLDER_ID のフォルダ内に
 *   テスト会社A/[TEST-001] テスト案件
 * というフォルダが作成されれば成功です。
 * ============================================================
 */
function testCreateDealFolder() {
  // M1_Companiesにテスト会社を1行追加してからテスト
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // テストデータをM1に追加
  const m1Sheet = ss.getSheetByName("M1_Companies");
  m1Sheet.appendRow(["TEST-C01", "テスト会社A", "", "顧客", "", "", "", "", "", "", 1.3, "テスト用"]);

  // テストデータをT1に追加
  const t1Sheet = ss.getSheetByName("T1_Deals");
  t1Sheet.appendRow(["TEST-001", "テスト案件", "オーダーメイド工具", "", "",
                     "新規受付", "TEST-C01", "", "", "", "",
                     false, "", false, "",
                     new Date(), "", new Date(), "", "", "テスト用"]);

  // createDealFolder を実行
  const result = createDealFolder("TEST-001", "テスト案件", "TEST-C01");
  Logger.log("結果: " + result);

  // テストデータを削除
  const m1Last = m1Sheet.getLastRow();
  const t1Last = t1Sheet.getLastRow();
  m1Sheet.deleteRow(m1Last);
  t1Sheet.deleteRow(t1Last);

  Logger.log("テストデータを削除しました。上記のURLにフォルダが作成されていれば成功です。");
}
