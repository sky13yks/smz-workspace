# 案件管理システム (メンテ特化・工具詳細型) - データベース設計図（ER図）

工具の「製造番号」を主キー（ユニークな名前）とし、詳細なスペック情報（諸元）とワーク図面、仕入先・顧客などを相互に紐づけた最新のデータベース設計図です。

## ER図（エンティティ・リレーションシップ図）

```mermaid
erDiagram
    %% ==========================================
    %% ユーザー入力の起点（トランザクション）
    %% ==========================================
    
    DEALS_LOGS {
        string ログID PK "主キー: L-XXXX"
        string 大分類 "工具 / 加工 / 中古機械 / 新品機械 / 修理 (Enum)"
        string アクション "見積 / メンテ登録 / ログ記録 (Enum)"
        string 会社ID FK "【静的】顧客マスタ参照"
        string 担当者ID FK "【静的】スタッフマスタ参照"
        datetime 発生日時
    }

    MACHINE_MAINT_LOGS {
        string メンテID PK "主キー: MM-XXXX"
        string 機械ID FK "【資産】機械マスタ参照"
        string ログID FK "活動ログへの参照"
        date 作業日
        string 作業ステータス
    }
    
    MACHINE_MAINT_DETAILS {
        string 詳細ID PK
        string メンテID FK "親: MACHINE_MAINT_LOGS"
        string 現場写真_URL "AppSheetで撮影"
        string 作業メモ "写真に対応する内容"
    }

    TOOL_MAINT_LOGS {
        string メンテID PK "主キー: TM-XXXX"
        string 工具製造番号 FK "【資産】工具マスタ参照"
        string ログID FK "活動ログへの参照"
        decimal 研磨量 "mm単位 (0.5mm超過で加算)"
        string コーティング膜種 "TiN / TiAlN / TiCN / Mercury 等"
        decimal 算出価格 "マスタから自動計算"
        string 価格補正理由 "研磨量による変動など"
    }

    DOCUMENTS_ESTIMATE {
        string 書類ID PK
        string ログID FK
        string 種類 "見積書 / 請求書"
        decimal 合計金額
    }
    
    DOCUMENTS_LINE_ITEMS {
        string 明細ID PK
        string 書類ID FK
        string 項目名
        decimal 金額
    }

    %% ==========================================
    %% 資産管理・マスタ（静的データ）
    %% ==========================================

    MASTER_MACHINES {
        string 機械ID PK "製造番号（シリアル）"
        string 会社ID FK
        string 機械名称
        string 型式
    }

    %% ワーク諸元・図面マスタ（工具と紐づく）
    MASTER_WORK_SPECS {
        string 諸元ID PK "主キー: WS-XXXX"
        string ワーク図面URL "ワーク図面のリンク"
        string ワーク名称_備考
    }

    %% 工具の個体管理（詳細化）
    MASTER_TOOLS {
        string 製造番号 PK "主キー兼名前 (ユニーク)"
        string 仕入先_会社ID FK "メーカー/仕入先 (参照: COMPANIES)"
        string 顧客_会社ID FK "納品先/顧客 (参照: COMPANIES)"
        string 諸元ID FK "ワーク図面・諸元 (参照: WORK_SPECS)"
        string 工具図面URL "工具図面のリンク"
        string 材質
        decimal モジュールピッチ
        decimal 圧力角
        string ねじれ方向
        int 条数
        decimal 外径 "価格算出・仕様確認用"
        decimal 厚み "価格算出・仕様確認用"
        decimal 内径 "仕様確認用"
    }

    MASTER_TOOL_PRICING {
        string 価格ID PK
        string 区分 "研磨 / コーティング"
        decimal 外径_mm
        decimal 厚み_mm
        string コーティング種別 "TiN / TiAlN 等 (研磨の場合は空)"
        decimal 基本価格 "研磨(0.5mm迄) or コーティング基本"
        decimal 加算単価 "研磨0.5mm毎の加算額"
    }

    MASTER_COMPANIES {
        string 会社ID PK
        string 会社名
        string 取引区分 "仕入先 / 顧客 等"
    }
    
    MASTER_STAFF {
        string 担当者ID PK
        string 氏名
    }

    %% ==========================================
    %% リレーションシップ
    %% ==========================================
    MASTER_MACHINES ||--o{ MACHINE_MAINT_LOGS : "メンテ履歴"
    MACHINE_MAINT_LOGS ||--o{ MACHINE_MAINT_DETAILS : "写真とメモ (1:N)"
    
    %% 工具マスタの多角的なリレーション
    MASTER_COMPANIES ||--o{ MASTER_TOOLS : "仕入先として紐付く"
    MASTER_COMPANIES ||--o{ MASTER_TOOLS : "顧客として紐付く"
    MASTER_WORK_SPECS ||--o{ MASTER_TOOLS : "対象ワーク諸元 (図面)"
    
    MASTER_TOOLS ||--o{ TOOL_MAINT_LOGS : "個体ごとのメンテ履歴"
    MASTER_TOOL_PRICING ||--o{ TOOL_MAINT_LOGS : "価格算出の根拠"
    
    DEALS_LOGS ||--o{ MACHINE_MAINT_LOGS : "活動としてのメンテ"
    DEALS_LOGS ||--o{ TOOL_MAINT_LOGS : "活動としてのメンテ"
    
    DEALS_LOGS ||--o{ DOCUMENTS_ESTIMATE : "帳票生成"
    DOCUMENTS_ESTIMATE ||--o{ DOCUMENTS_LINE_ITEMS : "明細"
```

---

## 新設計のポイント（工具管理の高度化）

1.  **「製造番号」を主キー（一意の名前）へ変更**
    *   工具データベースの中心（ID）を `製造番号` とし、システム上で工具を指定する際は必ずこの製造番号を選択・参照するようにしました。
2.  **詳細な基本スペック（仕様）の網羅**
    *   材質、モジュールピッチ、圧力角、ねじれ方向、条数、外径、厚み、内径といった専門的な変動パラメータを工具個体の属性として完全に保持します。
    *   このデータ群をもとに、価格算出や後続の再製作などの業務を精緻に自動化可能です。
3.  **多角的な相互リンケージ（リレーションの網の目化）**
    *   **仕入先（メーカー）** と **顧客（納品先）** を両方とも `MASTER_COMPANIES` から参照（Ref）するようにし、1つの工具画面から「どこで作り、どこへ納めているか」を一目で把握できるようにしました。
    *   新しいテーブルとして **`MASTER_WORK_SPECS`（ワーク諸元・図面マスタ）** を独立させ、ワーク図面とセットで諸元情報を一元管理。これを工具マスタに紐付けることで、「このワーク（諸元・図面）を削るための工具はこれ」という相互参照関係を構築しました。
    *   さらに、工具自体の図面は `工具図面URL` として工具マスタにダイレクトに紐づいています。
