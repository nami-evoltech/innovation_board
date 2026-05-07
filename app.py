# -*- coding: utf-8 -*-
from datetime import datetime
import os
import shutil
import sqlite3

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "innovation_board.sqlite3"))
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(BASE_DIR, "backups"))
STATUSES = ["未検討", "検討中", "採用候補", "採用", "保留", "却下"]
CATEGORIES = ["新規サービス", "業務改善", "マーケティング", "技術活用", "パートナー連携", "その他"]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-innovation-board")
app.config["JSON_AS_ASCII"] = False


def get_db():
    if "db" not in g:
        database_dir = os.path.dirname(DATABASE)
        if database_dir:
            os.makedirs(database_dir, exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            meeting_date TEXT NOT NULL DEFAULT '',
            objective TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            theme_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'その他',
            author TEXT NOT NULL DEFAULT '',
            vote_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '未検討',
            impact INTEGER NOT NULL DEFAULT 1,
            confidence INTEGER NOT NULL DEFAULT 1,
            ease INTEGER NOT NULL DEFAULT 1,
            ice_score INTEGER NOT NULL DEFAULT 1,
            good_points TEXT NOT NULL DEFAULT '',
            concerns TEXT NOT NULL DEFAULT '',
            expected_effect TEXT NOT NULL DEFAULT '',
            next_action TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES ideas (id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS status_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idea_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (idea_id) REFERENCES ideas (id) ON DELETE CASCADE
        );
        """
    )
    ensure_schema()
    db.commit()


def has_column(table, column):
    rows = get_db().execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def ensure_schema():
    db = get_db()
    if not has_column("ideas", "theme_id"):
        db.execute("ALTER TABLE ideas ADD COLUMN theme_id INTEGER")


@app.before_request
def ensure_db():
    init_db()


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def backup_database(label):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"innovation_board-{label}-{timestamp}.sqlite3")
    get_db().commit()
    shutil.copy2(DATABASE, backup_path)
    return backup_path


def to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def score_from_form():
    impact = max(1, min(10, to_int(request.form.get("impact"), 1)))
    confidence = max(1, min(10, to_int(request.form.get("confidence"), 1)))
    ease = max(1, min(10, to_int(request.form.get("ease"), 1)))
    return impact, confidence, ease, impact * confidence * ease


def idea_form_data():
    impact, confidence, ease, ice_score = score_from_form()
    status = request.form.get("status") or "未検討"
    category = request.form.get("category") or "その他"
    theme_id = to_int(request.form.get("theme_id"), 0) or None
    return {
        "theme_id": theme_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "category": category if category in CATEGORIES else "その他",
        "author": request.form.get("author", "").strip(),
        "vote_count": max(0, to_int(request.form.get("vote_count"), 0)),
        "status": status if status in STATUSES else "未検討",
        "impact": impact,
        "confidence": confidence,
        "ease": ease,
        "ice_score": ice_score,
        "good_points": request.form.get("good_points", "").strip(),
        "concerns": request.form.get("concerns", "").strip(),
        "expected_effect": request.form.get("expected_effect", "").strip(),
        "next_action": request.form.get("next_action", "").strip(),
        "memo": request.form.get("memo", "").strip(),
    }


def fetch_idea(idea_id):
    idea = get_db().execute(
        """
        SELECT ideas.*, themes.name AS theme_name
        FROM ideas
        LEFT JOIN themes ON themes.id = ideas.theme_id
        WHERE ideas.id = ?
        """,
        (idea_id,),
    ).fetchone()
    if idea is None:
        flash("指定されたアイデアは見つかりません。", "error")
    return idea


def fetch_themes():
    return get_db().execute(
        """
        SELECT
            themes.*,
            COUNT(ideas.id) AS idea_count,
            SUM(CASE WHEN ideas.vote_count > 0 THEN 1 ELSE 0 END) AS voted_idea_count,
            SUM(CASE WHEN ideas.id IS NOT NULL AND ideas.vote_count = 0 THEN 1 ELSE 0 END) AS unvoted_idea_count,
            COALESCE(SUM(ideas.vote_count), 0) AS vote_total
        FROM themes
        LEFT JOIN ideas ON ideas.theme_id = themes.id
        GROUP BY themes.id
        ORDER BY themes.meeting_date DESC, themes.updated_at DESC
        """
    ).fetchall()


def fetch_theme(theme_id):
    theme = get_db().execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
    if theme is None:
        flash("指定されたテーマは見つかりません。", "error")
    return theme


@app.route("/")
def dashboard():
    db = get_db()
    recent_themes = db.execute(
        """
        SELECT
            themes.*,
            COUNT(ideas.id) AS idea_count,
            SUM(CASE WHEN ideas.vote_count > 0 THEN 1 ELSE 0 END) AS voted_idea_count,
            SUM(CASE WHEN ideas.id IS NOT NULL AND ideas.vote_count = 0 THEN 1 ELSE 0 END) AS unvoted_idea_count,
            COALESCE(SUM(ideas.vote_count), 0) AS vote_total
        FROM themes
        LEFT JOIN ideas ON ideas.theme_id = themes.id
        GROUP BY themes.id
        ORDER BY themes.meeting_date DESC, themes.updated_at DESC
        LIMIT 5
        """
    ).fetchall()
    ranking_themes = db.execute(
        """
        SELECT
            themes.*,
            COUNT(ideas.id) AS idea_count,
            SUM(CASE WHEN ideas.vote_count > 0 THEN 1 ELSE 0 END) AS voted_idea_count,
            SUM(CASE WHEN ideas.id IS NOT NULL AND ideas.vote_count = 0 THEN 1 ELSE 0 END) AS unvoted_idea_count,
            COALESCE(SUM(ideas.vote_count), 0) AS vote_total
        FROM themes
        JOIN ideas ON ideas.theme_id = themes.id
        GROUP BY themes.id
        ORDER BY themes.meeting_date DESC, themes.updated_at DESC
        """
    ).fetchall()
    theme_rankings = []
    for theme in ranking_themes:
        top_ideas = db.execute(
            """
            SELECT * FROM ideas
            WHERE theme_id = ?
            ORDER BY vote_count DESC, updated_at DESC
            """,
            (theme["id"],),
        ).fetchall()
        top_idea = top_ideas[0] if top_ideas else None
        voted_rate = round(((theme["voted_idea_count"] or 0) / theme["idea_count"]) * 100) if theme["idea_count"] else 0
        theme_rankings.append({"theme": theme, "ideas": top_ideas, "top_idea": top_idea, "voted_rate": voted_rate})
    return render_template("dashboard.html", recent_themes=recent_themes, theme_rankings=theme_rankings)


@app.route("/themes")
def themes():
    return render_template("themes.html", themes=fetch_themes())


@app.route("/themes/new", methods=["GET", "POST"])
def new_theme():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("テーマ名は必須です。", "error")
            return render_template("theme_form.html", theme=request.form, mode="new")
        timestamp = now_text()
        db = get_db()
        db.execute(
            """
            INSERT INTO themes (name, meeting_date, objective, memo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                request.form.get("meeting_date", "").strip(),
                request.form.get("objective", "").strip(),
                request.form.get("memo", "").strip(),
                timestamp,
                timestamp,
            ),
        )
        db.commit()
        flash("テーマを登録しました。", "success")
        return redirect(url_for("themes"))
    return render_template("theme_form.html", theme=None, mode="new")


@app.route("/themes/<int:theme_id>/edit", methods=["GET", "POST"])
def edit_theme(theme_id):
    theme = fetch_theme(theme_id)
    if theme is None:
        return redirect(url_for("themes"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("テーマ名は必須です。", "error")
            return render_template("theme_form.html", theme=request.form, mode="edit")
        timestamp = now_text()
        db = get_db()
        db.execute(
            """
            UPDATE themes SET
                name = ?, meeting_date = ?, objective = ?, memo = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                name,
                request.form.get("meeting_date", "").strip(),
                request.form.get("objective", "").strip(),
                request.form.get("memo", "").strip(),
                timestamp,
                theme_id,
            ),
        )
        db.commit()
        flash("テーマを更新しました。", "success")
        return redirect(url_for("theme_detail", theme_id=theme_id))
    return render_template("theme_form.html", theme=theme, mode="edit")


@app.route("/themes/<int:theme_id>/delete", methods=["POST"])
def delete_theme(theme_id):
    theme = fetch_theme(theme_id)
    if theme is None:
        return redirect(url_for("themes"))
    db = get_db()
    timestamp = now_text()
    backup_database("before-theme-delete")
    db.execute("UPDATE ideas SET theme_id = NULL, updated_at = ? WHERE theme_id = ?", (timestamp, theme_id))
    db.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
    db.commit()
    flash("テーマを削除しました。紐づいていた付箋項目はテーマなしに戻しました。", "success")
    return redirect(url_for("themes"))


@app.route("/themes/<int:theme_id>", methods=["GET", "POST"])
def theme_detail(theme_id):
    theme = fetch_theme(theme_id)
    if theme is None:
        return redirect(url_for("themes"))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("付箋項目は必須です。", "error")
            return redirect(url_for("theme_detail", theme_id=theme_id))
        timestamp = now_text()
        vote_count = max(0, to_int(request.form.get("vote_count"), 0))
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO ideas (
                theme_id, title, description, category, author, vote_count, status,
                impact, confidence, ease, ice_score, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 1, ?, ?)
            """,
            (
                theme_id,
                title,
                request.form.get("description", "").strip(),
                "その他",
                request.form.get("author", "").strip(),
                vote_count,
                "未検討",
                timestamp,
                timestamp,
            ),
        )
        db.execute("UPDATE themes SET updated_at = ? WHERE id = ?", (timestamp, theme_id))
        db.commit()
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify(
                {
                    "ok": True,
                    "idea": {
                        "id": cursor.lastrowid,
                        "title": title,
                        "vote_count": vote_count,
                        "updated_at": timestamp,
                        "detail_url": url_for("idea_detail", idea_id=cursor.lastrowid),
                        "delete_url": url_for("delete_idea", idea_id=cursor.lastrowid),
                    },
                }
            )
        flash("付箋項目を登録しました。", "success")
        return redirect(url_for("theme_detail", theme_id=theme_id, focus="idea"))

    ideas_for_theme = get_db().execute(
        """
        SELECT * FROM ideas
        WHERE theme_id = ?
        ORDER BY vote_count DESC, updated_at DESC
        """,
        (theme_id,),
    ).fetchall()
    return render_template("theme_detail.html", theme=theme, ideas=ideas_for_theme, categories=CATEGORIES)


@app.route("/ideas")
def ideas():
    flash("付箋項目はテーマ詳細画面で確認してください。", "error")
    return redirect(url_for("themes"))


@app.route("/ideas/new", methods=["GET", "POST"])
def new_idea():
    flash("付箋項目はテーマ詳細画面から追加してください。", "error")
    return redirect(url_for("themes"))


@app.route("/ideas/<int:idea_id>")
def idea_detail(idea_id):
    idea = fetch_idea(idea_id)
    if idea is None:
        return redirect(url_for("ideas"))
    db = get_db()
    comments = db.execute("SELECT * FROM comments WHERE idea_id = ? ORDER BY created_at DESC", (idea_id,)).fetchall()
    logs = db.execute("SELECT * FROM status_logs WHERE idea_id = ? ORDER BY created_at DESC", (idea_id,)).fetchall()
    return render_template("detail.html", idea=idea, comments=comments, logs=logs, statuses=STATUSES)


@app.route("/ideas/<int:idea_id>/deep-dive", methods=["POST"])
def update_deep_dive(idea_id):
    idea = fetch_idea(idea_id)
    if idea is None:
        return redirect(url_for("themes"))
    timestamp = now_text()
    db = get_db()
    db.execute(
        """
        UPDATE ideas SET
            description = ?, good_points = ?, concerns = ?, expected_effect = ?,
            next_action = ?, memo = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            request.form.get("description", "").strip(),
            request.form.get("good_points", "").strip(),
            request.form.get("concerns", "").strip(),
            request.form.get("expected_effect", "").strip(),
            request.form.get("next_action", "").strip(),
            request.form.get("memo", "").strip(),
            timestamp,
            idea_id,
        ),
    )
    db.commit()
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "updated_at": timestamp})
    flash("メモを更新しました。", "success")
    return redirect(url_for("idea_detail", idea_id=idea_id))


@app.route("/ideas/<int:idea_id>/edit", methods=["GET", "POST"])
def edit_idea(idea_id):
    idea = fetch_idea(idea_id)
    if idea is None:
        return redirect(url_for("ideas"))
    if request.method == "POST":
        data = idea_form_data()
        if not data["title"]:
            flash("アイデア名は必須です。", "error")
            return render_template("form.html", idea=data, statuses=STATUSES, categories=CATEGORIES, themes=fetch_themes(), mode="edit")
        timestamp = now_text()
        db = get_db()
        db.execute(
            """
            UPDATE ideas SET
                theme_id = ?, title = ?, description = ?, category = ?, author = ?, vote_count = ?,
                status = ?, impact = ?, confidence = ?, ease = ?, ice_score = ?,
                good_points = ?, concerns = ?, expected_effect = ?, next_action = ?,
                memo = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["theme_id"], data["title"], data["description"], data["category"], data["author"],
                data["vote_count"], data["status"], data["impact"], data["confidence"], data["ease"],
                data["ice_score"], data["good_points"], data["concerns"], data["expected_effect"],
                data["next_action"], data["memo"], timestamp, idea_id,
            ),
        )
        if idea["status"] != data["status"]:
            db.execute(
                """
                INSERT INTO status_logs (idea_id, old_status, new_status, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (idea_id, idea["status"], data["status"], request.form.get("status_reason", "").strip(), timestamp),
            )
        db.commit()
        flash("アイデアを更新しました。", "success")
        return redirect(url_for("idea_detail", idea_id=idea_id))
    return render_template("form.html", idea=idea, statuses=STATUSES, categories=CATEGORIES, themes=fetch_themes(), mode="edit")


@app.route("/ideas/<int:idea_id>/delete", methods=["POST"])
def delete_idea(idea_id):
    idea = fetch_idea(idea_id)
    if idea is None:
        return redirect(url_for("themes"))

    db = get_db()
    backup_database("before-idea-delete")
    db.execute("DELETE FROM comments WHERE idea_id = ?", (idea_id,))
    db.execute("DELETE FROM status_logs WHERE idea_id = ?", (idea_id,))
    db.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    if idea["theme_id"]:
        db.execute("UPDATE themes SET updated_at = ? WHERE id = ?", (now_text(), idea["theme_id"]))
    db.commit()
    flash("付箋項目を削除しました。", "success")

    if idea["theme_id"]:
        return redirect(url_for("theme_detail", theme_id=idea["theme_id"]))
    return redirect(url_for("themes"))


@app.route("/ideas/<int:idea_id>/comments", methods=["POST"])
def add_comment(idea_id):
    idea = fetch_idea(idea_id)
    if idea is None:
        return redirect(url_for("ideas"))
    comment = request.form.get("comment", "").strip()
    if comment:
        get_db().execute(
            "INSERT INTO comments (idea_id, comment, created_by, created_at) VALUES (?, ?, ?, ?)",
            (idea_id, comment, request.form.get("created_by", "").strip(), now_text()),
        )
        get_db().commit()
        flash("コメントを追加しました。", "success")
    else:
        flash("コメント内容を入力してください。", "error")
    return redirect(url_for("idea_detail", idea_id=idea_id))


@app.route("/history")
def history():
    keyword = request.args.get("keyword", "").strip()
    db = get_db()
    sql = """
        SELECT logs.*, ideas.title, ideas.category, themes.name AS theme_name
        FROM status_logs logs
        JOIN ideas ON ideas.id = logs.idea_id
        LEFT JOIN themes ON themes.id = ideas.theme_id
        WHERE 1 = 1
    """
    params = []
    if keyword:
        sql += " AND (ideas.title LIKE ? OR logs.reason LIKE ? OR ideas.category LIKE ? OR themes.name LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
    sql += " ORDER BY logs.created_at DESC"
    logs = db.execute(sql, params).fetchall()
    archived = db.execute(
        """
        SELECT ideas.*, themes.name AS theme_name
        FROM ideas
        LEFT JOIN themes ON themes.id = ideas.theme_id
        WHERE status IN ('採用', '保留', '却下')
        ORDER BY ideas.updated_at DESC
        """
    ).fetchall()
    return render_template("history.html", logs=logs, archived=archived)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
