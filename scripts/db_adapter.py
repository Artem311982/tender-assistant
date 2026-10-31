import os
import sqlite3
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOCAL_KEY_PATH = os.path.join(PROJECT_ROOT, "key", "DATABASE_URL.nv.txt")

def _load_local_db_url():
    if os.path.exists(LOCAL_KEY_PATH):
        try:
            with open(LOCAL_KEY_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def _normalize_supabase_pooler_url(url):
    if not url:
        return url
    m = re.search(r'db\.([a-z0-9]+)\.supabase\.co', url)
    project_ref = m.group(1) if m else "ixrbpktmwyuvaseetbyb"
    # Convert direct domain or eu-central pooler to working IPv4 Pooler
    if "db." in url or "pooler.supabase.com" in url or "aws-0-" in url:
        url = re.sub(r'@[^:/]+:[0-9]+', '@aws-0-eu-west-2.pooler.supabase.com:5432', url)
        # Ensure tenant identifier is in username
        if f".{project_ref}" not in url:
            url = re.sub(r'://postgres:', f'://postgres.{project_ref}:', url)
    return url

DATABASE_URL = _normalize_supabase_pooler_url(os.environ.get("DATABASE_URL") or _load_local_db_url())
IS_VERCEL = bool(os.environ.get("VERCEL"))

if IS_VERCEL:
    TMP_ROOT = "/tmp"
    MEMORY_DIR = os.path.join(TMP_ROOT, "memory")
else:
    MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")

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

            # Translate SQLite scalar MAX(a, b) to PostgreSQL GREATEST(a, b)
            if "MAX(0," in clean_q or "MAX(0 ," in clean_q:
                q = re.sub(r"\bMAX\s*\(\s*0\s*,", "GREATEST(0,", q, flags=re.IGNORECASE)
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
