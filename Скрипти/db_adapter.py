import os
import sqlite3
import re

DEFAULT_SUPABASE_URL = "postgresql://postgres:yDcqYOiP8AarvtXY@db.ixrbpktmwyuvaseetbyb.supabase.co:5432/postgres?sslmode=require"
DATABASE_URL = os.environ.get("DATABASE_URL") or DEFAULT_SUPABASE_URL
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
IS_VERCEL = bool(os.environ.get("VERCEL"))

if IS_VERCEL:
    TMP_ROOT = "/tmp"
    MEMORY_DIR = os.path.join(TMP_ROOT, "memory")
else:
    MEMORY_DIR = os.path.join(PROJECT_ROOT, "Пам'ять")

DB_PATH = os.path.join(MEMORY_DIR, "tender_assistant.db")
os.makedirs(MEMORY_DIR, exist_ok=True)


if DATABASE_URL:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        psycopg2 = None

    class PgCursorWrapper:
        def __init__(self, cur):
            self._cur = cur
            self._lastrowid = None

        def execute(self, query, params=None):
            q = query.replace("?", "%s")
            clean_q = q.strip().upper()

            # Handle SQLite "INSERT OR REPLACE" / "INSERT OR IGNORE" translations for PostgreSQL
            if "INSERT OR REPLACE INTO SESSIONS" in clean_q:
                q = "INSERT INTO sessions (token, user_id, created_at) VALUES (%s, %s, %s) ON CONFLICT (token) DO UPDATE SET user_id = EXCLUDED.user_id, created_at = EXCLUDED.created_at"
            elif "INSERT OR REPLACE INTO SETTINGS" in clean_q:
                q = "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
            elif "INSERT OR IGNORE INTO SETTINGS" in clean_q:
                q = "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING"
            elif clean_q.startswith("INSERT OR IGNORE INTO "):
                q = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", q, flags=re.IGNORECASE) + " ON CONFLICT DO NOTHING"
            elif clean_q.startswith("INSERT OR REPLACE INTO "):
                q = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", q, flags=re.IGNORECASE)

            clean_q = q.strip().upper()

            # Handle cur.lastrowid emulation via RETURNING id for INSERT statements with auto-id tables
            has_id_table = any(f"INTO {t}" in clean_q for t in ["USERS", "ORDERS", "FORMS", "FEEDBACK_MESSAGES", "PASSWORD_RESETS"])
            if has_id_table and "RETURNING" not in clean_q and "DO NOTHING" not in clean_q:
                q = q.rstrip(" ;") + " RETURNING id;"
                if params is None:
                    self._cur.execute(q)
                else:
                    self._cur.execute(q, params)
                try:
                    row = self._cur.fetchone()
                    if row and "id" in row:
                        self._lastrowid = row["id"]
                except Exception:
                    self._lastrowid = None
                return self._cur

            if params is None:
                return self._cur.execute(q)
            return self._cur.execute(q, params)

        def executemany(self, query, seq_of_parameters):
            q = query.replace("?", "%s")
            return self._cur.executemany(q, seq_of_parameters)

        def fetchone(self):
            return self._cur.fetchone()

        def fetchall(self):
            return self._cur.fetchall()

        @property
        def lastrowid(self):
            return self._lastrowid

        @property
        def rowcount(self):
            return self._cur.rowcount

        def close(self):
            return self._cur.close()

    class PgConnectionWrapper:
        def __init__(self, conn):
            self._conn = conn

        def cursor(self):
            return PgCursorWrapper(self._conn.cursor(cursor_factory=RealDictCursor))

        def commit(self):
            return self._conn.commit()

        def rollback(self):
            return self._conn.rollback()

        def close(self):
            return self._conn.close()

    def get_db():
        dsn = DATABASE_URL.strip()
        if "sslmode=" not in dsn:
            conn = psycopg2.connect(dsn, sslmode="require")
        else:
            conn = psycopg2.connect(dsn)
        return PgConnectionWrapper(conn)

else:
    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
