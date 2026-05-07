# InnovationBoard

ブレスト後の会議テーマ、付箋アイデア、ドット投票、ICE評価を記録する Flask アプリです。

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

このアプリは Flask のサーバーアプリです。ローカルでは SQLite、本番では `DATABASE_URL` を設定して PostgreSQL に接続できます。Netlify の静的サイトホスティングではそのまま動かないため、Render の Python Web Service で動かします。

`render.yaml` を含めているため、Render では Blueprint としてこのリポジトリを接続できます。

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --bind 0.0.0.0:$PORT app:app`
- Environment Variable: `DATABASE_URL` に Neon の接続URLを設定

`DATABASE_URL` がない場合は、ローカル用の SQLite ファイル `innovation_board.sqlite3` を使います。
