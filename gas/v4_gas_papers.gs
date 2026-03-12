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
 * @returns {string} 生成されたPDFのURL
 */
function generatePaperPdf(paperId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // ── 1. T2_Papers から帳票ヘッダ取得 ──────────────────────────
  const t2Sheet = ss.getSheetByName("T2_Papers");
  const t2Data  = t2Sheet.getDataRange().getValues();
  const t2H     = t2Data[0];
  const paperRow = t2Data.find((r, i) => i > 0 && r[t2H.indexOf("帳票ID")] === paperId);
  if (!paperRow) throw new Error("帳票ID が見つかりません: " + paperId);

  const paperType   = paperRow[t2H.indexOf("種別")];
  const issueDate   = paperRow[t2H.indexOf("発行日")] || new Date();
  const expireDate  = paperRow[t2H.indexOf("有効期限")] || "";
  const dealId      = paperRow[t2H.indexOf("案件ID")];
  const companyId   = paperRow[t2H.indexOf("相手先会社ID")];
  const totalAmount = paperRow[t2H.indexOf("合計金額")] || 0;
  const remarks     = paperRow[t2H.indexOf("備考")] || "";

  // ── 2. M1_Companies から相手先会社名取得 ─────────────────────
  const m1Sheet = ss.getSheetByName("M1_Companies");
  const m1Data  = m1Sheet.getDataRange().getValues();
  const m1H     = m1Data[0];
  const companyRow = m1Data.find((r, i) => i > 0 && r[m1H.indexOf("会社ID")] === companyId);
  const companyName = companyRow ? companyRow[m1H.indexOf("会社名")] + " 御中" : "御中";

  // ── 3. T1_Deals から案件名・担当者取得 ───────────────────────
  const t1Sheet = ss.getSheetByName("T1_Deals");
  const t1Data  = t1Sheet.getDataRange().getValues();
  const t1H     = t1Data[0];
  const dealRow = t1Data.find((r, i) => i > 0 && r[t1H.indexOf("案件ID")] === dealId);
  const dealName    = dealRow ? dealRow[t1H.indexOf("案件名")] : "";
  const dealFolderUrl = dealRow ? dealRow[t1H.indexOf("ドライブフォルダURL")] : "";

  // ── 4. T2D_PaperLines から明細行取得 ─────────────────────────
  const t2dSheet = ss.getSheetByName("T2D_PaperLines");
  const t2dData  = t2dSheet.getDataRange().getValues();
  const t2dH     = t2dData[0];
  const lines = t2dData.filter((r, i) => i > 0 && r[t2dH.indexOf("帳票ID")] === paperId);

  // ── 5. テンプレートSSをコピーして一時ファイル作成 ──────────────
  const sourceFile = DriveApp.getFileById(PAPER_TEMPLATE_ID);
  const tempFolder = DriveApp.getFolderById(TEMP_PDF_FOLDER_ID);
  const tempFile   = sourceFile.makeCopy(`${paperId}_tmp`, tempFolder);
  const tempFileId = tempFile.getId();
  const sheetTemp  = SpreadsheetApp.openById(tempFileId).getSheets()[0];

  // ── 6. テンプレートへデータ書き込み ──────────────────────────
  sheetTemp.getRange("B4").setValue(companyName);
  sheetTemp.getRange("H4").setValue(issueDate);
  sheetTemp.getRange("H5").setValue(expireDate);
  sheetTemp.getRange("I9").setValue(paperId);
  sheetTemp.getRange("B9").setValue("件名: " + dealName);

  const DETAIL_START_ROW = 15;
  lines.forEach((line, idx) => {
    const row = DETAIL_START_ROW + idx;
    sheetTemp.getRange(row, 2).setValue(line[t2dH.indexOf("項目名")]);
    sheetTemp.getRange(row, 5).setValue(line[t2dH.indexOf("数量")]);
    sheetTemp.getRange(row, 6).setValue(line[t2dH.indexOf("単位")]);
    sheetTemp.getRange(row, 7).setValue(line[t2dH.indexOf("単価")]);
    sheetTemp.getRange(row, 8).setValue(line[t2dH.indexOf("金額")]);
  });

  if (remarks) sheetTemp.getRange("B" + (DETAIL_START_ROW + lines.length + 3)).setValue("備考: " + remarks);

  SpreadsheetApp.flush();

  // ── 7. PDF出力 ────────────────────────────────────────────────
  const exportUrl = `https://docs.google.com/spreadsheets/d/${tempFileId}/export?exportFormat=pdf&format=pdf&size=A4&portrait=true&fitw=true&sheetnames=false&printtitle=false&pagenumbers=false`;
  const token    = ScriptApp.getOAuthToken();
  const pdfBlob  = UrlFetchApp.fetch(exportUrl, { headers: { Authorization: "Bearer " + token } })
                              .getBlob().setName(`${paperType}_${paperId}.pdf`);

  // ── 8. 案件フォルダに保存（フォルダURLがあればそこへ、なければTEMPフォルダへ）─
  let saveFolder = tempFolder;
  if (dealFolderUrl) {
    try {
      const folderId = dealFolderUrl.match(/[-\w]{25,}/)?.[0];
      if (folderId) saveFolder = DriveApp.getFolderById(folderId);
    } catch(e) { /* フォルダ取得失敗時はTEMPに保存 */ }
  }
  const pdfFile = saveFolder.createFile(pdfBlob);
  const pdfUrl  = pdfFile.getUrl();

  // ── 9. T2_PapersにPDF_URLを書き戻す ──────────────────────────
  const pdfUrlCol = t2H.indexOf("PDF_URL");
  if (pdfUrlCol !== -1) {
    const rowIdx = t2Data.findIndex((r, i) => i > 0 && r[t2H.indexOf("帳票ID")] === paperId);
    if (rowIdx > 0) t2Sheet.getRange(rowIdx + 1, pdfUrlCol + 1).setValue(pdfUrl);
  }

  // ── 10. 後処理（一時ファイル削除）────────────────────────────
  DriveApp.getFileById(tempFileId).setTrashed(true);

  return `PDF Generated: ${pdfUrl}`;
}
