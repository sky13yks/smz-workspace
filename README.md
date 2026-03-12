# SMZ 受発注管理システム

株式会社清水商會 — 内部開発ツール

---

## このリポジトリの役割

| フォルダ | 内容 |
|---------|------|
| `gas/` | Google Apps Scriptのソースコード |
| `docs/` | 設計ドキュメント・仕様書 |
| `.devcontainer/` | Docker開発環境の設定 |

> **コアシステム（AppSheet / Spreadsheet）はGoogleのクラウド上で動いています。**
> このリポジトリは「GASコードのバージョン管理」が主な目的です。

---

## 初回セットアップ（全員が行う）

### ステップ 1: 必要なツールをインストール

以下をまだインストールしていない場合はインストールしてください。

| ツール | ダウンロード先 |
|--------|--------------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |
| VS Code | https://code.visualstudio.com/ |
| VS Code拡張「Dev Containers」| VS Code内で `Dev Containers` を検索してインストール |

### ステップ 2: このリポジトリをクローン

ターミナル（Macの「ターミナル」アプリ）を開いて以下を実行：

```bash
cd ~
git clone https://github.com/sky13yks/smz-workspace.git
cd smz-workspace
```

### ステップ 3: VS CodeでDev Containerを開く

```
1. VS Codeで smz-workspace フォルダを開く
2. 左下の「><」ボタンをクリック（または F1キー）
3. 「Dev Containers: Reopen in Container」を選択
4. Dockerイメージのビルドが始まる（初回のみ数分かかります）
5. ✅ SMZ開発環境の準備完了！ と表示されたら成功
```

### ステップ 4: Googleアカウントにログイン（初回のみ）

Dev Container内のターミナルで：

```bash
clasp login
# ブラウザが開くのでGoogleアカウント（会社アカウント）でログイン
```

### ステップ 5: GASスクリプトIDを設定

```bash
cd gas
cp .clasp.json.example .clasp.json
# .clasp.json を開いてスクリプトIDを入力
# ※ スクリプトIDはGASエディタのURL末尾の文字列
```

> ⚠️ `.clasp.json` はGitにpushしません（セキュリティのため）
> スクリプトIDはリーダーから別途共有してもらってください。

---

## 日常の開発フロー

### 作業開始時

```bash
# 1. developブランチを最新にする
git checkout develop
git pull origin develop

# 2. 自分の作業ブランチを作る
git checkout -b feature/作業内容の名前
# 例: git checkout -b feature/工具マスタ追加

# 3. GASの最新コードをダウンロード（念のため）
cd gas && clasp pull
```

### コードを変更したあと

```bash
# 1. GASにアップロードしてテスト
cd gas && clasp push

# 2. 問題なければGitにコミット
git add gas/変更したファイル.gs
git commit -m "feat: 工具マスタの採番ロジックを追加"

# 3. GitHubにpush
git push origin feature/作業内容の名前

# 4. GitHubでPull Request（プルリクエスト）を作成
# → develop ブランチへのマージを依頼
```

### コミットメッセージのルール

```
feat: 新機能の追加
fix:  バグの修正
docs: ドキュメントの更新
test: テストの追加・修正
refactor: コードの整理（機能変更なし）

例:
feat: 見積依頼テーブルの登録処理を追加
fix: 採番ロジックで連番がズレる問題を修正
docs: CLAUDE.mdの未決事項を更新
```

---

## ブランチ構成

```
main      ← 本番稼働中のコード（リーダーのみマージ可）
develop   ← 開発の統合ブランチ（PRでマージ）
feature/* ← 各自の作業ブランチ（自由にpush可）
```

---

## GitHubリポジトリの設定（リーダーが行う）

以下をGitHub上で設定してください：

### Branch Protection Rules（ブランチ保護）

1. GitHub → Settings → Branches → Add rule
2. `main` に以下を設定：
   - [x] Require a pull request before merging
   - [x] Require approvals（1人以上のレビュー必須）
   - [x] Restrict who can push（リーダーのみ）
3. `develop` に以下を設定：
   - [x] Require a pull request before merging

### Collaborators（メンバー招待）

Settings → Collaborators → Add people で4人全員を招待

---

## よく使うコマンド早見表

| やりたいこと | コマンド |
|------------|---------|
| GASにコードを反映 | `cd gas && clasp push` |
| GASのコードを取得 | `cd gas && clasp pull` |
| GASのログを見る | `cd gas && clasp logs` |
| GASのエディタを開く | `cd gas && clasp open` |
| 最新コードを取得 | `git pull origin develop` |
| 変更を保存 | `git add . && git commit -m "メッセージ"` |
| GitHubに送る | `git push origin ブランチ名` |

---

## 困ったときは

1. このリポジトリの `docs/` フォルダに設計ドキュメントがあります
2. VS Code内でClaude Codeに聞く（`CLAUDE.md` を自動的に読んで答えてくれます）
3. リーダー（山口）に相談

---

## 関連リポジトリ

- [smz-HP](https://github.com/sky13yks/smz-HP) — 会社ホームページ（Next.js）
