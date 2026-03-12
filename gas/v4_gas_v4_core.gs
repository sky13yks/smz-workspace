/**
 * 歯車商社向け 基幹業務システム v4.0 GAS バックエンド・コア
 * 
 * 機能:
 * 1. Webhook 受信 (doPost)
 * 2. Google Drive フォルダ自動生成
 * 3. PDF 帳票自動生成 (Template 方式)
 */

const CONFIG = {
  PARENT_FOLDER_ID: "ここに親フォルダのIDを入力", // ルートフォルダ
  TEMPLATE_DOC_ID: "ここに見積書テンプレートのIDを入力",
  OUTPUT_FOLDER_ID: "ここにPDF出力先のIDを入力"
};

/**
 * AppSheet からの Webhook (POST) をメインエントリポイントとして処理
 */
function doPost_legacy_v2(e) {
  const data = JSON.parse(e.postData.contents);
  const action = data.action; // AppSheet Webhook で "action" パラメータを送る
  const record = data.record;

  try {
    let result;
    switch (action) {
      case "CREATE_FOLDER":
        result = createDealFolder(record);
        break;
      case "GENERATE_PDF":
        result = generatePaperPDF(record);
        break;
      default:
        throw new Error("Unknown action: " + action);
    }
    
    return ContentService.createTextOutput(JSON.stringify({status: "success", data: result}))
      .setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", message: error.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * [Google Drive 連携] 案件別のフォルダ構造を自動作成
 */
function createDealFolder_v2(record) {
  // パス: [顧客名]/[案件ID_案件名]
  const customerName = record.CompanyName || "不明な顧客";
  const dealInfo = record.DealID + "_" + (record.DealName || "無題の案件");
  
  const parentFolder = DriveApp.getFolderById(CONFIG.PARENT_FOLDER_ID);
  
  // 顧客フォルダの取得または作成
  let customerFolder;
  const it = parentFolder.getFoldersByName(customerName);
  if (it.hasNext()) {
    customerFolder = it.next();
  } else {
    customerFolder = parentFolder.createFolder(customerName);
  }
  
  // 案件フォルダの作成
  const dealFolder = customerFolder.createFolder(dealInfo);
  
  // 必要ならサブフォルダを作成（図面、見積、写真等）
  dealFolder.createFolder("01_図面資料");
  dealFolder.createFolder("02_見積・注文");
  dealFolder.createFolder("03_写真・報告書");
  
  return { folderUrl: dealFolder.getUrl(), folderId: dealFolder.getId() };
}

/**
 * [PDF 生成] Google ドキュメントテンプレートを置換して PDF 出力
 */
function generatePaperPDF(record) {
  const template = DriveApp.getFileById(CONFIG.TEMPLATE_DOC_ID);
  const outputFolder = DriveApp.getFolderById(CONFIG.OUTPUT_FOLDER_ID);
  
  // テンプレートをコピーして一時ファイル作成
  const tempFile = template.makeCopy("TEMP_" + record.PaperID, outputFolder);
  const doc = DocumentApp.openById(tempFile.getId());
  const body = doc.getBody();
  
  // プレースホルダを置換 (例: {{CompanyName}})
  // record の全キーをループして置換
  for (let key in record) {
    body.replaceText("{{" + key + "}}", record[key] || "");
  }
  
  doc.saveAndClose();
  
  // PDF 出力
  const pdfBlob = tempFile.getAs(MimeType.PDF);
  const pdfFile = outputFolder.createFile(pdfBlob).setName(record.PaperType + "_" + record.PaperID + ".pdf");
  
  // 一時ファイル削除
  tempFile.setTrashed(true);
  
  return { pdfUrl: pdfFile.getUrl(), pdfId: pdfFile.getId() };
}
