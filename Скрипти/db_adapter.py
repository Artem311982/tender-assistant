import os
import sqlite3
import re

DATABASE_URL = os.environ.get("DATABASE_URL")
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
        # Fallback if psycopg2 is not installed
        psycopg2 = None

    class PgCursorWrapper:
        def __init__(self, cur):
            self._cur = cur
            self._lastrowid = None

        def execute(self, query, params=None):
            # Convert SQLite '?' placeholders to PostgreSQL '%s'
            q = query.replace("?", "%s")
            clean_q = q.strip().upper()

            # Handle cur.lastrowid emulation via RETURNING id for INSERT statements
            if clean_q.startswith("INSERT INTO ") and "RETURNING" not in clean_q:
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
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return PgConnectionWrapper(conn)

else:
    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
