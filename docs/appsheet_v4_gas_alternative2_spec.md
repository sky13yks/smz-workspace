# GAS実装仕様書: 帳票ディープコピー & PDF自動生成 (v4.0 改善案2)

AppSheetの制約を回避し、堅牢で柔軟な受発注システムを構築するため、最も複雑な「明細データの複製（ディープコピー）」と「指定フォーマットのPDF生成」をGoogle Apps Script (GAS) に委譲します。

---

## 🚀 1. 帳票ディープコピー（見積 → 注文 等）の実装方針

AppSheet上ではボタンを押すだけ。裏側でGASがスプレッドシートを直接操作し、親テーブル(T2)と子テーブル(T2D)を同時に複製することで、完全なディープコピーを実現します。

### 処理フロー
1. **[AppSheet]** ユーザーがT2（帳票管理）の特定の行で「複製ボタン（種類：Action）」を押す。
2. **[AppSheet]** その行の `複製フラグ` カラム（一時的なトリガー用）を TRUE にする。
3. **[AppSheet: Bot]** `複製フラグ = TRUE` を検知し、WebhookでGASエンドポイント（`doPost`）へ対象の `帳票ID` と `複製先種別（例：注文書）` を送信する。
4. **[GAS]** Webhookを受信。
5. **[GAS]** T2シートから元帳票データを読み取り、新しい「帳票ID」を採番してT2シートに新規行を追加（親の複製）。
6. **[GAS]** T2Dシートから元帳票IDに紐づく明細行を全て抽出。
7. **[GAS]** 新しい「明細ID」と新しい「帳票ID」を付与して、T2Dシートに明細行を一括追加（子の複製）。
8. **[GAS]** （オプション）複製元の `複製フラグ` を FALSE に戻す。

### GASモジュール構成案 (`v4_gas_papers.gs`)
```javascript
// Webhookエントリポイント
function doPost(e) {
  const payload = JSON.parse(e.postData.contents);
  const actionType = payload.actionType; // "DEEP_COPY" or "GENERATE_PDF"
  
  if (actionType === "DEEP_COPY") {
    handleDeepCopy(payload.sourcePaperId, payload.targetType);
  } else if (actionType === "GENERATE_PDF") {
    handleGeneratePdf(payload.paperId);
  }
  return ContentService.createTextOutput("Success");
}

// ディープコピーメイン処理
function handleDeepCopy(sourcePaperId, targetType) {
  // 1. 新しい帳票IDの生成 (P-YYYYMMDD-XXX)
  // 2. T2から元データ取得＆新規行作成
  // 3. T2Dから元明細取得
  // 4. T2Dへ新規明細行一括追加
}
```

---

## 📄 2. スプレッドシートを雛形としたPDF生成の実装方針

AppSheet標準のPDF作成機能はレイアウトの自由度が低いため、「専用のスプレッドシートテンプレート」を用いた美しい帳票出力を実現します。

### 処理フロー
1. **[事前準備]** Googleドライブ上に「見積書テンプレート.xlsx（またはスプレッドシート）」を用意しておく。セルの位置（例: `B4`に会社名、`A15`から明細開始）を固定。
2. **[AppSheet]** ユーザーが「PDF出力」ボタンを押す。
3. **[AppSheet: Bot]** WebhookでGASへ送信（`帳票ID`）。
4. **[GAS]** T2（ヘッダ）およびT2D（明細）からデータを取得。
5. **[GAS]** テンプレートファイルをシステム用の一時作業フォルダへコピー。
6. **[GAS]** コピーしたスプレッドシートを開き、特定セルへデータを流し込む（`Range.setValue()`等）。
7. **[GAS]** 明細行が複数ある場合は、テンプレートの明細行部分に行を挿入しながらデータを書き込む。
8. **[GAS]** スプレッドシートのPDFエクスポート用URL（`export?exportFormat=pdf`）を利用し、PDFバイナリを取得。
9. **[GAS]** T1の `案件ID` に紐づくDriveの案件専用フォルダへ、生成したPDFファイルを保存。
10. **[GAS]** （オプション）T5（図面・資料管理）へPDFファイルのURL/パスを自動登録。

### メリット
*   **完全なレイアウト再現**: 現在使っているExcelフォーマットをそのままスプレッドシート化するだけで、ハンコ欄や細かな表組みを100%再現できます。
*   **AppSheetの縛りからの脱却**: 複雑な `<<Start>>` などのテンプレート構文に悩まされることなく、JavaScript (App Script) の柔軟な制御で改ページや小計の計算が可能です。

---

## 🔄 3. 全体アーキテクチャのアップデート (Alternative 2)

この「GAS依存型アーキテクチャ」を採用することで、AppSheetは**純粋な「データ入力・閲覧用フロントエンド」および「業務トリガー発火装置」**として機能が純化されます。

*   **フロントエンド (AppSheet)**
    *   現場でのデータ入力（写真、メモ）
    *   ファイルのアップロード
    *   各種アクションの発火（ボタン押下によるWebhook送信）
*   **バックエンド (GAS & スプレッドシート)**
    *   データの保存（テーブル群）
    *   複雑なデータ操作（ディープコピー、在庫計算等）
    *   外部ファイル生成（PDF帳票のレイアウト・出力・保存）
    *   フォルダ構造の自動管理（Drive）
*   **レポーティング (Looker Studio)**
    *   経営層向けの売上集計グラフ
    *   事務員向の一覧閲覧ダッシュボード

この体制により、**「AppSheetが苦手なことは最初からやらせない」**という、極めて安定した開発・運用が可能になります。
