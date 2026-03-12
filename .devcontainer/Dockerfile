FROM node:20-bullseye-slim

# 必要なツールをインストール
RUN apt-get update && apt-get install -y \
    git \
    curl \
    vim \
    && rm -rf /var/lib/apt/lists/*

# clasp（Google Apps Script CLI）をグローバルインストール
RUN npm install -g @google/clasp@2.4.2

# 作業ディレクトリ
WORKDIR /workspace

# 非rootユーザーで動かす（セキュリティ対策）
USER node
