# AppSheet データベース・スキーマ設計書（全15テーブル）

AppSheetエディタの `Data > Columns` 画面において、各テーブルの項目をどのように設定すべきかを厳密に定義した設計図です。
自動化の要となる **Type (型)**、**Key (主キー)**、**Label (表示名)**、**Formula (自動計算式)**、**Initial Value (初期値)** を網羅しています。

---

## 1. トランザクション・ログ系（起点となるデータ）

### 1. 活動ログ (DealsLogs)
アプリ起動時のエントランス画面となる最重要テーブルです。
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| ログID | Text | ✅ | | **(I.V)** `"L-" & TEXT(TODAY(), "YYMMDD") & "-" & UNIQUEID()` | ID自動採番 |
| 件名_概要 | Text | | ✅ | | |
| 大分類 | Enum | | | | Values: 工具, 中古機械, 新品機械, 修理 |
| アクション | Enum | | | | 大分類に応じたアクションのリスト |
| 会社ID | Ref | | | | **Source**: `M1. 顧客_仕入先` |
| 担当者ID | Ref | | | | **Source**: `M3. スタッフ` |
| 発生日時 | DateTime | | | **(I.V)** `NOW()` | |
| 備考_メモ | LongText| | | | |

### 2. 機械メンテ (MachineMaint)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| メンテID | Text | ✅ | | **(I.V)** `"MM-" & UNIQUEID()` | |
| 機械ID | Ref | | ✅ | | **Source**: `M6. 機械マスタ` |
| ログID | Ref | | | | **Source**: `1. 活動ログ`<br>*(Is a part of: ON 推奨)* |
| 作業日 | Date | | | **(I.V)** `TODAY()` | |
| 作業ステータス | Enum | | | | Values: 予約, 作業中, 完了 |
| 総括メモ | LongText| | | | |

### 3. 機械メンテ詳細 (MaintDetails)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| 詳細ID | Text | ✅ | | **(I.V)** `"MD-" & UNIQUEID()` | |
| メンテID | Ref | | | | **Source**: `2. 機械メンテ`<br>*(Is a part of: ON 必須)* |
| 現場写真_URL | Image | | ✅ | | AppSheetから直接撮影 |
| 作業メモ | LongText| | | | |

### 4. 工具メンテ (ToolMaint)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| メンテID | Text | ✅ | | **(I.V)** `"TM-" & UNIQUEID()` | |
| 工具製造番号 | Ref | | ✅ | | **Source**: `M5. 工具マスタ` |
| ログID | Ref | | | | **Source**: `1. 活動ログ`<br>*(Is a part of: ON 推奨)* |
| 研磨量 | Decimal | | | | 小数点以下入力 |
| コーティング膜種 | Enum | | | | Values: TiN, TiAlN, TiCN, ... |
| 算出価格 | Price | | | **(Formula)** *※別紙『魔法の数式集』の算出式* | 0.5mmステップ自動計算 |
| 価格補正理由 | Text | | | | `Show_If`: `[研磨量] > 0`等 |
| 次回メンテ推奨日| Date | | | | |

### 5. 見積_注文書 (EstimateOrders)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| 書類ID | Text | ✅ | | **(I.V)** `"DOC-" & UNIQUEID()` | |
| ログID | Ref | | | | **Source**: `1. 活動ログ`<br>*(Is a part of: ON 推奨)* |
| 書類種別 | Enum | | | | Values: 見積書, 注文書, 請求書 |
| 件名 | Text | | ✅ | **(I.V)** `[ログID].[件名_概要]` | 親からテキストを引き継ぎ |
| 提出日 | Date | | | **(I.V)** `TODAY()` | |
| 有効期限 | Date | | | **(I.V)** `TODAY() + 30` | 30日後を初期値に |
| 合計金額 | Price | | | **(Formula)** `SUM([Related 書類明細s][金額])`| 子明細からのロールアップ |
| PDFファイルURL | File | | | | GAS生成結果格納用 |
| 備考 | LongText| | | | |

### 6. 書類明細 (LineItems)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| 明細ID | Text | ✅ | | **(I.V)** `"LI-" & UNIQUEID()` | |
| 書類ID | Ref | | | | **Source**: `5. 見積_注文書`<br>*(Is a part of: ON 必須)* |
| 項目名_作業内容| Text | | ✅ | | |
| 数量 | Number | | | **(I.V)** `1` | |
| 単位 | Enum | | | **(I.V)** `"式"` | Values: 個, 本, 式 |
| 単価 | Price | | | | |
| 金額 | Price | | | **(Formula)** `[数量] * [単価]` | |
| 備考 | Text | | | | |

### 7. 契約_仕様書 (ContractsSpecs)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| _RowNumber | Number | | | | |
| 書類ID | Text | ✅ | | **(I.V)** `"SPEC-" & UNIQUEID()` | |
| ログID | Ref | | | | **Source**: `1. 活動ログ`<br>*(Is a part of: ON 推奨)* |
| 書類種別 | Enum | | | | Values: 売買契約書, 仕様書, 議事録 |
| 対象機械_機器名| Text | | ✅ | | |
| 取引条件_特記事項| LongText| | | | |
| 添付ファイルURL | File | | | | ユーザーアップロード用 |

---

## 2. マスター系（裏側で管理する静的データ）

### M1. 顧客_仕入先 (Companies)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 会社ID | Text | ✅ | | **(I.V)** `"C-" & UNIQUEID()` | |
| 会社名 | Text | | ✅ | | **（活動ログ等で表示される名前）** |
| 取引区分 | EnumList| | | | Values: 顧客, 仕入先, メーカー |

### M2. 名刺 (Contacts)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 名刺ID | Text | ✅ | | **(I.V)** `"CON-" & UNIQUEID()` | |
| 会社ID | Ref | | | | **Source**: `M1. 顧客_仕入先` |
| 氏名 | Text | | ✅ | | |

### M3. スタッフ (Staff)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 担当者ID | Text | ✅ | | **(I.V)** `"S-" & UNIQUEID()` | |
| 氏名 | Text | | ✅ | | **（活動ログ等で表示される名前）** |
| 電子印影URL | Image | | | | |

### M4. ワーク諸元 (WorkSpecs)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 諸元ID | Text | ✅ | | **(I.V)** `"WS-" & UNIQUEID()` | |
| ワーク名称 | Text | | ✅ | | |
| ワーク図面URL | File | | | | |

### M5. 工具マスタ (Tools)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 製造番号 | Text | ✅ | ✅ | | 主キーとLabelを兼ねる |
| 仕入先_会社ID | Ref | | | | **Source**: `M1. 顧客_仕入先` |
| 納品先_会社ID | Ref | | | | **Source**: `M1. 顧客_仕入先` |
| 諸元ID | Ref | | | | **Source**: `M4. ワーク諸元` |
| 外径 | Decimal | | | | 各種パラメータ等 |

### M6. 機械マスタ (Machines)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 機械ID_製造番号| Text | ✅ | ✅ | | 主キーとLabelを兼ねる |
| 会社ID | Ref | | | | **Source**: `M1. 顧客_仕入先` |

### M7. 工具価格マスタ (ToolPricing)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 価格ID | Text | ✅ | | **(I.V)** `UNIQUEID()` | |
| 区分 | Enum | | ✅ | | Values: 研磨, コーティング |
| 外径_mm | Decimal | | | | |
| 厚み_mm | Decimal | | | | |

### M8. 設定マスタ (Settings)
| COLUMN NAME | TYPE | KEY | LABEL | FORMULA / INITIAL VALUE | 備考 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 設定キー | Text | ✅ | ✅ | | |
| 設定値 | Text | | | | |

---

## 💡 設定時の重要ポイント
1.  **Key**: そのテーブルで「絶対に他と被らない、一つだけ特定できる」列です。1テーブルに1つ必ずチェックが必要です。
2.  **Label**: 他のテーブルから「Ref（参照）」された時に、**画面上に文字として表示される列**です。例えば活動ログで「C-001」というIDではなく「〇〇株式会社」と表示させるには、`M1. 顧客_仕入先`の「会社名」にLabelチェックをします。
3.  **Is a part of**: 子テーブル（明細や写真など）を持つ設定です。Ref 型にした際に出てくる `Is a part of?` にチェックを入れると、親の入力画面の中に子の追加（New）ボタンができるため、UXが劇的に向上します。
