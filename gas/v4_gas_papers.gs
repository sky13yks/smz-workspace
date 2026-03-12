/**
 * ============================================================================
 * 案件管理システム V4.0 - GAS Papers モジュール (v4_gas_papers.gs)
 * ============================================================================
 * 
 * 帳票（T2_Papers）と明細（T2D_PaperLines）に関する複雑な処理を担当します。
 *  1. ディープコピー (見積書から注文書などの作成)
 *  2. スプレッドシートを雛形としたPDF生成とDrive保存
 */

// テンプレートSSのID（ダミー）
const PAPER_TEMPLATE_ID = "ここに帳票テンプレートのスプレッドシートIDを指定してください"; 
// PDF保存先の一時作業用フォルダID
const TEMP_PDF_FOLDER_ID = "ここにPDF作成用のテンポラリフォルダIDを指定してください";

/**
 * 帳票（親）と帳票明細（子）を同時に複製し、新しい種別（例：発注書）として登録する
 * @param {string} sourcePaperId - コピー元の帳票ID (例: P-12345)
 * @param {string} targetType - コピー先の種別 (例: "注文書")
 * @returns {string} 実行結果メッセージ
 */
function copyPaperAndLines(sourcePaperId, targetType) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const t2Sheet = ss.getSheetByName("T2_Papers");
  const t2dSheet = ss.getSheetByName("T2D_PaperLines");
  
  // 1. 新しい帳票ID（親）の採番
  const timestamp = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyyMMddHHmmss");
  const newPaperId = "P-" + timestamp; // 例: P-20260306123045
  
  // 2. コピー元の親帳票データを取得
  const t2Data = t2Sheet.getDataRange().getValues();
  const t2Headers = t2Data[0];
  const paperIdCol = t2Headers.indexOf("帳票ID");
  
  let sourceRowIdx = -1;
  let sourceRowData = null;
  for (let i = 1; i < t2Data.length; i++) {
    if (t2Data[i][paperIdCol] === sourcePaperId) {
      sourceRowIdx = i;
      sourceRowData = t2Data[i].slice();
      break;
    }
  }
  
  if (!sourceRowData) throw new Error("Source paper ID not found.");
  
  // 3. コピー先用の行データを整形（「種別」や「元帳票ID」を上書き）
  const typeCol = t2Headers.indexOf("種別");
  const sourceCol = t2Headers.indexOf("元帳票ID");
  const dateCol = t2Headers.indexOf("発行日");
  const copyFlagCol = t2Headers.indexOf("複製フラグ");
  
  sourceRowData[paperIdCol] = newPaperId;
  sourceRowData[typeCol] = targetType;
  sourceRowData[sourceCol] = sourcePaperId;       // 元のIDをセット
  sourceRowData[dateCol] = new Date();            // 日付は今日に更新
  if (copyFlagCol !== -1) sourceRowData[copyFlagCol] = false; // フラグは落とす
  
  t2Sheet.appendRow(sourceRowData);
  
  // 4. 子明細データの取得と複製
  const t2dData = t2dSheet.getDataRange().getValues();
  const t2dHeaders = t2dData[0];
  const t2dPaperIdCol = t2dHeaders.indexOf("帳票ID");
  const t2dLineIdCol = t2dHeaders.indexOf("明細ID");
  
  let linesToAppend = [];
  for (let i = 1; i < t2dData.length; i++) {
    if (t2dData[i][t2dPaperIdCol] === sourcePaperId) {
      let newLine = t2dData[i].slice();
      // 新しい明細ID(PL-) と、親の帳票ID(P-) をセット
      newLine[t2dLineIdCol] = "PL-" + timestamp + "-" + i;
      newLine[t2dPaperIdCol] = newPaperId;
      linesToAppend.push(newLine);
    }
  }
  
  if (linesToAppend.length > 0) {
    // 効率的に一括追加
    t2dSheet.getRange(t2dSheet.getLastRow() + 1, 1, linesToAppend.length, t2dHeaders.length)
            .setValues(linesToAppend);
  }
  
  // 5. AppSheetでトリガーとなった元のチェックボックス(複製フラグ)をリセット
  if (copyFlagCol !== -1) {
    t2Sheet.getRange(sourceRowIdx + 1, copyFlagCol + 1).setValue(false);
  }
  
  return `Deep copy successful. New Paper ID: ${newPaperId}`;
}


/**
 * 対象の帳票データをSSテンプレートに流し込み、PDF化してDriveに保存する
 * @param {string} paperId - PDF化する対象の帳票ID
 */
function generatePaperPdf(paperId) {
  // 1. スプレッドシートテンプレートのコピー
  const sourceFile = DriveApp.getFileById(PAPER_TEMPLATE_ID);
  const tempFolder = DriveApp.getFolderById(TEMP_PDF_FOLDER_ID);
  const tempFile = sourceFile.makeCopy(`${paperId}_output`, tempFolder);
  const tempFileId = tempFile.getId();
  
  const ssTemp = SpreadsheetApp.openById(tempFileId);
  const sheetTemp = ssTemp.getSheets()[0]; // 1つ目のシートを使用
  
  // 2. 元データの取得（T2, T2D, T1, M1等から情報を集約する処理）
  //    ※現状はダミーデータ流し込みのサンプルロジックですが、
  //    実運用ではSpreadsheetAppで関連データを引いてくる処理を書きます。
  
  const companyName = "株式会社〇〇 御中"; // 実際はM1から取得
  const details = [
    { name: "ホブカッター", qty: 2, price: 50000 },
    { name: "コーティング", qty: 2, price: 3000 }
  ];
  
  // 3. テンプレートへのデータ書き込み
  sheetTemp.getRange("B4").setValue(companyName);       // 宛先設定の例
  sheetTemp.getRange("H4").setValue(new Date());        // 発行日
  sheetTemp.getRange("I9").setValue(paperId);           // 番号
  
  let startRow = 15; // 明細開始行の例
  for (let i = 0; i < details.length; i++) {
    sheetTemp.getRange(startRow + i, 2).setValue(details[i].name);
    sheetTemp.getRange(startRow + i, 6).setValue(details[i].qty);
    sheetTemp.getRange(startRow + i, 8).setValue(details[i].price);
  }
  
  SpreadsheetApp.flush(); // 即時反映
  
  // 4. スプレッドシートをPDFとして出力
  const url = `https://docs.google.com/spreadsheets/d/${tempFileId}/export?exportFormat=pdf&format=pdf&size=A4&portrait=true&fitw=true&sheetnames=false&printtitle=false&pagenumbers=false`;
  const token = ScriptApp.getOAuthToken();
  const response = UrlFetchApp.fetch(url, { headers: { 'Authorization': 'Bearer ' + token } });
  const pdfBlob = response.getBlob().setName(`${paperId}.pdf`);
  
  // 5. T1_Dealsから案件フォルダのURL（ID）を逆引きし、そこに保存
  // （ここでは簡略化のためルートフォルダ保存）
  // 実際は DriveApp.getFolderById(targetFolderId).createFile(pdfBlob); を行います。
  const createdFile = DriveApp.getFolderById(TEMP_PDF_FOLDER_ID).createFile(pdfBlob);
  const pdfUrl = createdFile.getUrl();
  
  // 6. 後処理（テンポラリファイルの削除）
  DriveApp.getFileById(tempFileId).setTrashed(true);
  
  // 7. 生成されたPDFのURLを T5_Files（図面・資料管理）などに紐付けて記録する処理を繋げます
  // ...
  
  return `PDF Generated: ${pdfUrl}`;
}
