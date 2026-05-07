# -*- coding: utf-8 -*-
import argparse
import os
import sqlite3

import psycopg
from psycopg.rows import dict_row


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, "innovation_board.sqlite3")

TABLES = {
    "themes": ["id", "name", "meeting_date", "objective", "memo", "created_at", "updated_at"],
    "ideas": [
        "id", "theme_id", "title", "description", "category", "author", "vote_count", "status",
        "impact", "confidence", "ease", "ice_score", "good_points", "concerns", "expected_effect",
        "next_action", "memo", "created_at", "updated_at",
    ],
    "comments": ["id", "idea_id", "comment", "created_by", "created_at"],
    "status_logs": ["id", "idea_id", "old_status", "new_status", "reason", "created_at"],
}


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS themes (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    meeting_date TEXT NOT NULL DEFAULT '',
    objective TEXT NOT NULL DEFAULT '',
    memo TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    idea_id INTEGER NOT NULL,
    comment TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (idea_id) REFERENCES ideas (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS status_logs (
    id SERIAL PRIMARY KEY,
    idea_id INTEGER NOT NULL,
    old_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (idea_id) REFERENCES ideas (id) ON DELETE CASCADE
);
"""


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate local SQLite data to PostgreSQL.")
    parser.add_argument("--sqlite-path", default=os.environ.get("SQLITE_PATH", DEFAULT_SQLITE_PATH))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--replace", action="store_true", help="Delete existing PostgreSQL rows before importing.")
    return parser.parse_args()


def create_schema(pg):
    for statement in [item.strip() for item in SCHEMA_SQL.split(";") if item.strip()]:
        pg.execute(statement)


def destination_has_rows(pg):
    for table in TABLES:
        count = pg.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
        if count:
            return True
    return False


def reset_destination(pg):
    pg.execute("TRUNCATE status_logs, comments, ideas, themes RESTART IDENTITY CASCADE")


def copy_table(sqlite_db, pg, table, columns):
    rows = sqlite_db.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id").fetchall()
    if not rows:
        return 0

    column_sql = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    for row in rows:
        pg.execute(insert_sql, [row[column] for column in columns])
    return len(rows)


def reset_sequence(pg, table):
    pg.execute(
        """
        SELECT setval(
            pg_get_serial_sequence(%s, 'id'),
            COALESCE((SELECT MAX(id) FROM """ + table + """), 1),
            (SELECT COUNT(*) FROM """ + table + """) > 0
        )
        """,
        (table,),
    )


def main():
    args = parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required.")
    if not os.path.exists(args.sqlite_path):
        raise SystemExit(f"SQLite file not found: {args.sqlite_path}")

    sqlite_db = sqlite3.connect(args.sqlite_path)
    sqlite_db.row_factory = sqlite3.Row

    with psycopg.connect(args.database_url, row_factory=dict_row) as pg:
        create_schema(pg)
        if destination_has_rows(pg):
            if not args.replace:
                raise SystemExit("PostgreSQL already has data. Re-run with --replace to overwrite it.")
            reset_destination(pg)

        copied = {}
        for table, columns in TABLES.items():
            copied[table] = copy_table(sqlite_db, pg, table, columns)
            reset_sequence(pg, table)

        pg.commit()

    for table, count in copied.items():
        print(f"{table}: {count} rows")
    print("Migration complete.")


if __name__ == "__main__":
    main()
