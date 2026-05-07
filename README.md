# InnovationBoard

ブレスト後の会議テーマ、付箋アイデア、ドット投票、ICE評価、検討履歴を記録する Flask + SQLite アプリです。

## 前提条件

- Python 3.10 以上
- 文字コードは UTF-8 を前提にしています。
- HTML は `<meta charset="utf-8">` を指定しています。
- `.editorconfig` と `.gitattributes` で主要テキストファイルを UTF-8 として扱います。

## 起動方法

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

ブラウザで http://127.0.0.1:5000 を開きます。

## デプロイ

このアプリは Flask + SQLite のサーバーアプリです。Netlify の静的サイトホスティングではそのまま動かないため、Render などの Python Web サービスで動かします。

Render では次の設定を使います。

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
