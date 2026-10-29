import os
import shutil
import sys
import json
import sqlite3
import hashlib
import secrets
import base64
import urllib.parse
from datetime import datetime, timedelta
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import doc_generator
import prozorro_service
from db_adapter import get_db, DB_PATH, IS_VERCEL, DATABASE_URL

if IS_VERCEL:
    TMP_ROOT = "/tmp"
    INPUT_DIR = os.path.join(TMP_ROOT, "input")
    FORMS_UPLOAD_DIR = os.path.join(INPUT_DIR, "forms")
    USER_UPLOADS_DIR = os.path.join(INPUT_DIR, "user_uploads")
    RESULT_DIR = os.path.join(TMP_ROOT, "result")
    ORDERS_RESULT_DIR = os.path.join(RESULT_DIR, "orders")
    MEMORY_DIR = os.path.join(TMP_ROOT, "memory")
    STATIC_DIR = os.path.join(PROJECT_ROOT, "public")
else:
    INPUT_DIR = os.path.join(PROJECT_ROOT, "Вхідні дані")
    FORMS_UPLOAD_DIR = os.path.join(INPUT_DIR, "Завантажені_форми")
    USER_UPLOADS_DIR = os.path.join(INPUT_DIR, "Заповнені_форми_клієнтів")
    RESULT_DIR = os.path.join(PROJECT_ROOT, "Результат")
    ORDERS_RESULT_DIR = os.path.join(RESULT_DIR, "Заявки")
    MEMORY_DIR = os.path.join(PROJECT_ROOT, "Пам'ять")
    STATIC_DIR = os.path.join(SCRIPT_DIR, "static")

for d in [INPUT_DIR, FORMS_UPLOAD_DIR, USER_UPLOADS_DIR, RESULT_DIR, ORDERS_RESULT_DIR, MEMORY_DIR, STATIC_DIR]:
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass

SESSIONS = {}

DISPOSABLE_EMAIL_DOMAINS = {
    "tempmail.com", "temp-mail.org", "10minutemail.com", "guerrillamail.com",
    "guerrillamailblock.com", "mailinator.com", "trashmail.com", "yopmail.com",
    "sharklasers.com", "getairmail.com", "dispostable.com", "fakemailgenerator.com",
    "throwawaymail.com", "mohmal.com", "crazymailing.com", "nada.ltd",
    "generator.email", "dropmail.me", "fakemail.net", "burnermail.io", "tempmail.net",
    "temporary-mail.net", "tempmailo.com", "emailondeck.com", "inboxkitten.com"
}

REGISTRATION_IP_HISTORY = {}  # ip -> list of timestamps

DEFAULT_USER_PERMISSIONS = {
    "access_level": "full",  # 'full' | 'basic' | 'readonly' | 'custom'
    "can_create_orders": True,
    "can_prozorro_autofill": True,
    "can_docx_upload": True,
    "can_view_price_table": True,
    "can_download_main_doc": True,
    "can_download_annex_doc": True,
    "can_view_legal_variants": False,
    "can_edit_org_details": False
}


def parse_permissions(raw_json):
    perms = dict(DEFAULT_USER_PERMISSIONS)
    if raw_json:
        try:
            loaded = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            if isinstance(loaded, dict):
                perms.update(loaded)
        except Exception:
            pass
    return perms


def parse_authorized_persons(raw_json):
    if not raw_json:
        return []
    try:
        loaded = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
        if isinstance(loaded, list):
            res = []
            for item in loaded:
                s = str(item or "").strip()
                if s and s not in res:
                    res.append(s)
            return res
    except Exception:
        pass
    return []


def hash_password(pw):
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# get_db imported from db_adapter


def init_db():
    if DATABASE_URL:
        return
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            org_name TEXT DEFAULT '',
            edrpou TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            director_name TEXT DEFAULT '',
            director_title TEXT DEFAULT '',
            website TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            account_type TEXT DEFAULT 'user',
            delivery_override TEXT DEFAULT 'default',
            quota INTEGER DEFAULT 5,
            is_active INTEGER DEFAULT 1,
            permissions_json TEXT DEFAULT '',
            created_at TEXT
        )
    """)

    # Міграція для існуючої бази, якщо колонки permissions_json, account_type або authorized_persons_json ще не було
    cur.execute("PRAGMA table_info(users)")
    cols = [r["name"] for r in cur.fetchall()]
    if "permissions_json" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN permissions_json TEXT DEFAULT ''")
    if "account_type" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'user'")
    if "authorized_persons_json" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN authorized_persons_json TEXT DEFAULT '[]'")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            sender_name TEXT DEFAULT '',
            sender_email TEXT DEFAULT '',
            sender_org TEXT DEFAULT '',
            sender_edrpou TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            message TEXT NOT NULL,
            admin_reply TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            created_at TEXT,
            replied_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            fields_json TEXT NOT NULL,
            docx_template_path TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            form_id INTEGER NOT NULL,
            form_title TEXT DEFAULT '',
            is_released INTEGER DEFAULT 0,
            payment_status TEXT DEFAULT 'unpaid',
            input_data_json TEXT NOT NULL,
            benchmarks_json TEXT NOT NULL,
            stats_json TEXT NOT NULL,
            consultation_json TEXT NOT NULL,
            file1_name TEXT DEFAULT '',
            file1_path TEXT DEFAULT '',
            file2_name TEXT DEFAULT '',
            file2_path TEXT DEFAULT '',
            uploaded_docx_name TEXT DEFAULT '',
            admin_comment TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    default_settings = {
        "delivery_mode": "manual",
        "service_title": "Створення порівняння цін у системі Prozorro та обґрунтувань за Постановою КМУ № 710 і № 1178",
        "platform_name": "Тендерний помічник",
        "platform_subtitle": "",
        "logo_data_url": ""
    }
    for k, v in default_settings.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # Прибираємо згадку про "реальних оголошень" та прибираємо підпис "Порівняння цін у системі Prozorro..." із шапки за замовчуванням
    cur.execute(
        "UPDATE settings SET value = ? WHERE key = 'service_title' AND value LIKE '%реальних%'",
        (default_settings["service_title"],)
    )
    cur.execute(
        "UPDATE settings SET value = '' WHERE key = 'platform_subtitle' AND (value LIKE '%реальних%' OR value LIKE '%Порівняння цін у системі Prozorro%')"
    )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_perms_str = json.dumps(DEFAULT_USER_PERMISSIONS, ensure_ascii=False)

    cur.execute("SELECT COUNT(*) as cnt FROM users")
    if cur.fetchone()["cnt"] == 0:
        # 1. Головний адміністратор — Артем
        cur.execute("""
            INSERT INTO users (email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'admin', 'admin', 'auto', 999, 1, ?, ?)
        """, (
            "artemvolodymyrovych@gmail.com",
            hash_password("admin123"),
            "Артем Володимирович (Адміністратор)",
            "Аналітичний центр «Тендерний помічник»",
            "00000000",
            "+380960000000",
            "м. Миколаїв",
            "Артем Володимирович",
            "Керівник проєкту",
            "https://prozorro.gov.ua",
            full_perms_str,
            now_str
        ))

        # 2. Клієнт № 1 — НУК ім. адм. Макарова (окремий особистий кабінет клієнта)
        cur.execute("""
            INSERT INTO users (email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 'client', 'default', 25, 1, ?, ?)
        """, (
            "lyudmyla.shumova@nuos.edu.ua",
            hash_password("user123"),
            "Людмила ШУМОВА",
            "НАЦІОНАЛЬНИЙ УНІВЕРСИТЕТ КОРАБЛЕБУДУВАННЯ ІМЕНІ АДМІРАЛА МАКАРОВА",
            "02066753",
            "+380964141094",
            "54007, Україна, Миколаївська область, м. Миколаїв, просп. Героїв України, буд. 9",
            "Євген ТРУШЛЯКОВ",
            "Ректор Національного університету кораблебудування імені адмірала Макарова",
            "https://nuos.edu.ua",
            full_perms_str,
            now_str
        ))

    # Оновлюємо логін адміністратора на artemvolodymyrovych@gmail.com та логін/пароль НУК на lyudmyla.shumova@nuos.edu.ua / user123
    cur.execute("UPDATE users SET email = 'artemvolodymyrovych@gmail.com', account_type = 'admin' WHERE email = 'admin@tender.ua' OR role = 'admin'")
    cur.execute(
        "UPDATE users SET email = 'lyudmyla.shumova@nuos.edu.ua', password_hash = ?, account_type = 'client' WHERE email = 'client@nuos.edu.ua'",
        (hash_password("user123"),)
    )
    cur.execute("UPDATE users SET account_type = 'client' WHERE role != 'admin'")
    cur.execute("UPDATE users SET delivery_override = 'manual' WHERE role != 'admin' AND (delivery_override IS NULL OR delivery_override = '' OR delivery_override = 'default')")

    # Заповнюємо permissions_json тим користувачам, у кого він порожній
    cur.execute("UPDATE users SET permissions_json = ? WHERE permissions_json IS NULL OR permissions_json = ''", (full_perms_str,))

    # Початкові форми (без поля email)
    cur.execute("SELECT COUNT(*) as cnt FROM forms")
    if cur.fetchone()["cnt"] == 0:
        form1_fields = [
            {"key": "buyer_name", "label": "Найменування замовника", "type": "text", "required": True},
            {"key": "edrpou", "label": "Код ЄДРПОУ", "type": "text", "required": True},
            {"key": "subject_name", "label": "Конкретна назва предмета закупівлі", "type": "text", "required": True},
            {"key": "cpv_code", "label": "Код ДК 021:2015 (CPV 2008, IDT)", "type": "text", "required": True},
            {"key": "expected_value", "label": "Очікувана вартість предмета закупівлі (без ПДВ, грн)", "type": "number", "required": True},
            {"key": "quantity", "label": "Кількість (обсяг закупівлі)", "type": "number", "required": True},
            {"key": "unit_name", "label": "Одиниця виміру (Гкал, кВт·год, шт, послуга тощо)", "type": "text", "required": True},
            {"key": "tender_id", "label": "Ідентифікатор закупівлі в Prozorro (UA-... за наявності)", "type": "text", "required": False}
        ]
        f1_template_path = os.path.join(FORMS_UPLOAD_DIR, "Форма_1_Інформація_для_проведення_аналізу_цін.docx")
        doc_generator.generate_form_template_docx(
            "Інформація для проведення аналізу цін та формування обґрунтування підстав проведення закупівлі",
            form1_fields,
            f1_template_path
        )
        cur.execute("""
            INSERT INTO forms (title, description, fields_json, docx_template_path, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (
            "Форма № 1: Інформація для проведення аналізу цін (базова)",
            "Сформована на основі документа «Інформація для проведення аналізу цін.docx» з полями очікуваної вартості та обсягу закупівлі.",
            json.dumps(form1_fields, ensure_ascii=False),
            f1_template_path,
            now_str
        ))

        form2_fields = [
            {"key": "tender_id", "label": "Ідентифікатор закупівлі в Prozorro (UA-...)", "type": "text", "required": True},
            {"key": "plan_id", "label": "Ідентифікатор плану закупівлі в Prozorro", "type": "text", "required": False},
            {"key": "buyer_name", "label": "Найменування замовника", "type": "text", "required": True},
            {"key": "edrpou", "label": "Код ЄДРПОУ замовника", "type": "text", "required": True},
            {"key": "buyer_address", "label": "Місцезнаходження (юридична адреса) замовника", "type": "text", "required": True},
            {"key": "director_title", "label": "Посада керівника", "type": "text", "required": False},
            {"key": "director_name", "label": "Власне ім'я ПРІЗВИЩЕ керівника", "type": "text", "required": False},
            {"key": "authorized_person", "label": "Власне ім'я ПРІЗВИЩЕ уповноваженої особи", "type": "text", "required": True},
            {"key": "phone", "label": "Телефон уповноваженої особи", "type": "text", "required": False},
            {"key": "website", "label": "Офіційний веб-сайт замовника (для оприлюднення за Постановою № 710)", "type": "text", "required": False},
            {"key": "subject_name", "label": "Конкретна назва предмета закупівлі", "type": "text", "required": True},
            {"key": "cpv_code", "label": "Код ДК 021:2015 (CPV)", "type": "text", "required": True},
            {"key": "quantity", "label": "Кількість (плановий обсяг закупівлі)", "type": "number", "required": True},
            {"key": "unit_name", "label": "Одиниця виміру", "type": "text", "required": True},
            {"key": "expected_value", "label": "Очікувана вартість предмета закупівлі (без ПДВ, грн)", "type": "number", "required": True},
            {"key": "kekv", "label": "Код економічної класифікації видатків (КЕКВ)", "type": "text", "required": False},
            {"key": "delivery_term", "label": "Строк поставки товарів / надання послуг", "type": "text", "required": False},
            {"key": "delivery_address", "label": "Місця поставки (кожна адреса з нового рядка)", "type": "textarea", "required": False},
            {"key": "tech_specs", "label": "Технічні та якісні характеристики предмета закупівлі", "type": "textarea", "required": False}
        ]
        f2_template_path = os.path.join(FORMS_UPLOAD_DIR, "Форма_2_Повне_Обгрунтування_Постанова_710.docx")
        doc_generator.generate_form_template_docx(
            "Повна форма: Обґрунтування технічних характеристик, бюджетного призначення та очікуваної вартості (Постанова КМУ № 710)",
            form2_fields,
            f2_template_path
        )
        cur.execute("""
            INSERT INTO forms (title, description, fields_json, docx_template_path, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (
            "Форма № 2: Повна форма Обґрунтування (Постанова № 710 + Аналіз цін Prozorro)",
            "Розширена форма з усіма реквізитами замовника, місцями поставки та технічними характеристиками.",
            json.dumps(form2_fields, ensure_ascii=False),
            f2_template_path,
            now_str
        ))

    # Прибираємо поле email з усіх існуючих форм заявки на аналіз у БД та перегенеровуємо бланки .docx
    cur.execute("SELECT * FROM forms")
    existing_forms = cur.fetchall()
    for f_row in existing_forms:
        try:
            fid = f_row["id"]
            raw_fields = json.loads(f_row["fields_json"] or "[]")
            cleaned_fields = [
                fl for fl in raw_fields
                if fl.get("key") != "email"
                and "email" not in str(fl.get("label", "")).lower()
                and "електронна пошта" not in str(fl.get("label", "")).lower()
            ]
            tpath = f_row["docx_template_path"] or os.path.join(FORMS_UPLOAD_DIR, f"Форма_{fid}.docx")
            cur.execute("UPDATE forms SET fields_json = ?, docx_template_path = ? WHERE id = ?", (
                json.dumps(cleaned_fields, ensure_ascii=False),
                tpath,
                fid
            ))
            doc_generator.generate_form_template_docx(f_row["title"], cleaned_fields, tpath)
        except Exception:
            pass

    cur.execute("SELECT token, user_id FROM sessions")
    for r in cur.fetchall():
        SESSIONS[r["token"]] = r["user_id"]
    conn.commit()
    conn.close()


def should_auto_release(conn, user_row):
    override = (user_row["delivery_override"] or "default").lower()
    if override == "auto":
        return 1
    if override == "manual":
        return 0
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'delivery_mode'")
    row = cur.fetchone()
    mode = (row["value"] if row else "manual").lower()
    return 1 if mode == "auto" else 0


def serialize_user(u_row):
    d = dict(u_row)
    d.pop("password_hash", None)
    d["permissions"] = parse_permissions(d.pop("permissions_json", ""))
    d["authorized_persons"] = parse_authorized_persons(d.pop("authorized_persons_json", "[]"))
    return d


class TenderAppHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        now_s = datetime.now().strftime("%H:%M:%S")
        print(f"[{now_s}] {args[0]}", flush=True)

    def end_headers(self):
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file_download(self, file_path, download_name):
        if not file_path or not os.path.exists(file_path):
            self.send_json({"error": "Файл не знайдено на сервері"}, 404)
            return
        with open(file_path, "rb") as f:
            content = f.read()
        encoded_name = urllib.parse.quote(download_name)
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def get_current_user(self):
        auth = self.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
        else:
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "token" in qs:
                token = qs["token"][0]
        if not token:
            return None
        uid = SESSIONS.get(token)
        conn = get_db()
        cur = conn.cursor()
        if not uid:
            cur.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
            s_row = cur.fetchone()
            if s_row:
                uid = s_row["user_id"]
                SESSIONS[token] = uid
        if not uid:
            conn.close()
            return None
        cur.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (uid,))
        user = cur.fetchone()
        conn.close()
        return user

    def do_HEAD(self):
        self.do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html", "/admin", "/admin/"):
            index_file = os.path.join(STATIC_DIR, "index.html")
            if not os.path.exists(index_file):
                index_file = os.path.join(PROJECT_ROOT, "public", "index.html")
            if not os.path.exists(index_file):
                index_file = os.path.join(PROJECT_ROOT, "Скрипти", "static", "index.html")
            if os.path.exists(index_file):
                with open(index_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(content)
                return
            self.send_json({"error": "UI file missing"}, 404)
            return

        if path.startswith("/api/public/express-check"):
            qs = urllib.parse.parse_qs(parsed.query)
            q_text = qs.get("query", [""])[0].strip()
            cpv = qs.get("cpv", [""])[0].strip()
            if not q_text and not cpv:
                self.send_json({"error": "Вкажіть назву товару або код ДК 021:2015"}, 400)
                return
            try:
                items = prozorro_service.search_benchmarks_live(query_text=q_text, cpv_code=cpv, limit=6)
            except Exception:
                items = []
            prices = [float(it.get("unit_price_no_vat") or it.get("unit_price") or 0) for it in items if float(it.get("unit_price_no_vat") or it.get("unit_price") or 0) > 0]
            unit_names = [it.get("unit_name") for it in items if it.get("unit_name")]
            sample_unit = unit_names[0] if unit_names else "од."
            count = len(items)
            min_price = min(prices) if prices else 0.0
            max_price = max(prices) if prices else 0.0
            avg_price = (sum(prices) / len(prices)) if prices else 0.0

            self.send_json({
                "count": count,
                "months": 12,
                "min_price": round(min_price, 2),
                "max_price": round(max_price, 2),
                "avg_price": round(avg_price, 2),
                "query": q_text or cpv,
                "found_contracts": count > 0,
                "unit": sample_unit
            })
            return

        if path.startswith("/api/public/org-lookup"):
            qs = urllib.parse.parse_qs(parsed.query)
            edrpou = (qs.get("edrpou", [""])[0]).strip()
            if not edrpou or not edrpou.isdigit() or len(edrpou) not in (8, 10):
                self.send_json({"found": False, "error": "Невірний формат ЄДРПОУ/РНОКПП"}, 400)
                return
            
            org_name = None
            director_name = None
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT org_name, director_name FROM users WHERE edrpou = ? LIMIT 1", (edrpou,))
            db_row = cur.fetchone()
            conn.close()
            if db_row and db_row["org_name"]:
                org_name = db_row["org_name"]
                director_name = db_row["director_name"] or ""

            if not org_name:
                res = prozorro_service.lookup_org_by_edrpou(edrpou)
                if res:
                    org_name = res.get("name")
                    director_name = res.get("director") or ""

            if org_name:
                self.send_json({
                    "found": True,
                    "edrpou": edrpou,
                    "org_name": org_name,
                    "director_name": director_name
                })
            else:
                self.send_json({
                    "found": False,
                    "message": "Організацію за цим кодом не знайдено в базі або системі Prozorro"
                })
            return

        if path == "/api/public/info":
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM settings")
            settings = {r["key"]: r["value"] for r in cur.fetchall()}
            cur.execute("SELECT id, title, description, fields_json, is_active, created_at FROM forms WHERE is_active = 1")
            forms = []
            for r in cur.fetchall():
                forms.append({
                    "id": r["id"],
                    "title": r["title"],
                    "description": r["description"],
                    "fields": json.loads(r["fields_json"])
                })
            conn.close()
            self.send_json({"settings": settings, "forms": forms})
            return

        if path == "/api/me":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            self.send_json({"user": serialize_user(user)})
            return

        if path.startswith("/api/prozorro/lookup"):
            user = self.get_current_user()
            if user and user["role"] != "admin":
                perms = parse_permissions(user["permissions_json"])
                if not perms.get("can_prozorro_autofill", True):
                    self.send_json({"error": "Автозаповнення з Prozorro вимкнено для вашого рівня доступу адміністратором."}, 403)
                    return
            qs = urllib.parse.parse_qs(parsed.query)
            tid = qs.get("tender_id", [""])[0]
            res = prozorro_service.lookup_tender_by_id(tid)
            if not res:
                self.send_json({"found": False, "message": "Тендер не знайдено у системі Prozorro. Перевірте ідентифікатор або заповніть поля вручну."})
            else:
                self.send_json({"found": True, "data": res})
            return

        if path.startswith("/api/prozorro/search"):
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            qs = urllib.parse.parse_qs(parsed.query)
            q_text = qs.get("query", [""])[0]
            cpv = qs.get("cpv", [""])[0]
            items = prozorro_service.search_benchmarks_live(query_text=q_text, cpv_code=cpv, limit=8)
            self.send_json({"results": items})
            return

        if path.startswith("/api/forms/download/"):
            user = self.get_current_user()
            if user and user["role"] != "admin":
                perms = parse_permissions(user["permissions_json"])
                if not perms.get("can_docx_upload", True):
                    self.send_json({"error": "Робота з файлами форм .docx обмежена вашим рівнем доступу."}, 403)
                    return
            fid = path.split("/")[-1]
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM forms WHERE id = ?", (fid,))
            form = cur.fetchone()
            conn.close()
            if not form:
                self.send_json({"error": "Форму не знайдено"}, 404)
                return
            tpath = form["docx_template_path"]
            if not tpath or not os.path.exists(tpath):
                tpath = os.path.join(FORMS_UPLOAD_DIR, f"Форма_{form['id']}.docx")
                doc_generator.generate_form_template_docx(form["title"], json.loads(form["fields_json"]), tpath)
            self.send_file_download(tpath, os.path.basename(tpath))
            return

        if path == "/api/orders":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            perms = parse_permissions(user["permissions_json"])
            conn = get_db()
            cur = conn.cursor()
            if user["role"] == "admin":
                cur.execute("""
                    SELECT o.*, u.full_name as user_name, u.email as user_email, u.org_name as user_org
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    ORDER BY o.id DESC
                """)
            else:
                cur.execute("""
                    SELECT o.*, u.full_name as user_name, u.email as user_email, u.org_name as user_org
                    FROM orders o
                    LEFT JOIN users u ON o.user_id = u.id
                    WHERE o.user_id = ?
                    ORDER BY o.id DESC
                """, (user["id"],))

            rows = cur.fetchall()
            orders = []
            for r in rows:
                d = dict(r)
                d["input_data"] = json.loads(d.pop("input_data_json", "{}"))
                benchmarks = json.loads(d.pop("benchmarks_json", "[]"))
                stats = json.loads(d.pop("stats_json", "{}"))
                consult = json.loads(d.pop("consultation_json", "{}"))
                if user["role"] != "admin" and not d["is_released"]:
                    d["benchmarks"] = []
                    d["stats"] = {"unit_name": stats.get("unit_name", ""), "expected_value_no_vat": stats.get("expected_value_no_vat", 0)}
                    d["consultation"] = {}
                else:
                    d["benchmarks"] = benchmarks if (user["role"] == "admin" or perms.get("can_view_price_table", True)) else []
                    d["stats"] = stats
                    d["consultation"] = consult if (user["role"] == "admin" or perms.get("can_view_legal_variants", False)) else {}
                orders.append(d)
            conn.close()
            self.send_json({"orders": orders})
            return

        if path.startswith("/api/orders/download/"):
            parts = path.strip("/").split("/")
            if len(parts) < 5:
                self.send_json({"error": "Невірний URL"}, 400)
                return
            oid = parts[3]
            file_num = parts[4]
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            perms = parse_permissions(user["permissions_json"])
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM orders WHERE id = ?", (oid,))
            order = cur.fetchone()
            conn.close()
            if not order:
                self.send_json({"error": "Заявку не знайдено"}, 404)
                return
            if user["role"] != "admin":
                if order["user_id"] != user["id"]:
                    self.send_json({"error": "Доступ заборонено"}, 403)
                    return
                if not order["is_released"]:
                    self.send_json({"error": "Результат очікує погодження адміністратора"}, 403)
                    return
                if file_num == "1" and not perms.get("can_download_main_doc", True):
                    self.send_json({"error": "Скачування Файлу 1 (Основне Обґрунтування) не передбачено вашим рівнем доступу."}, 403)
                    return
                if file_num == "2" and not perms.get("can_download_annex_doc", True):
                    self.send_json({"error": "Скачування Файлу 2 (Додаток з порівнянням цін) не передбачено вашим рівнем доступу."}, 403)
                    return

            file_path = order["file1_path"] if file_num == "1" else order["file2_path"]
            download_name = order["file1_name"] if file_num == "1" else order["file2_name"]

            # Автоматична динамічна регенерація .docx на льоту, якщо файл відсутній на поточному сервері
            if not file_path or not os.path.exists(file_path):
                try:
                    input_data = json.loads(order["input_data_json"] or "{}")
                    benchmarks = json.loads(order["benchmarks_json"] or "[]")
                    f1_p, f2_p, f1_n, f2_n = doc_generator.generate_order_documents(oid, input_data, benchmarks, ORDERS_RESULT_DIR)
                    file_path = f1_p if file_num == "1" else f2_p
                    download_name = f1_n if file_num == "1" else f2_n
                except Exception as e:
                    print("Dynamic document generation failed:", e)

            self.send_file_download(file_path, download_name)
            return

        if path == "/api/admin/overview":
            user = self.get_current_user()
            if not user or user["role"] != "admin":
                self.send_json({"error": "Тільки для адміністратора"}, 403)
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT key, value FROM settings")
            settings = {r["key"]: r["value"] for r in cur.fetchall()}

            cur.execute("SELECT * FROM users ORDER BY id ASC")
            users = [serialize_user(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM forms ORDER BY id DESC")
            forms = []
            for r in cur.fetchall():
                fd = dict(r)
                fd["fields"] = json.loads(fd.pop("fields_json", "[]"))
                forms.append(fd)

            cur.execute("SELECT * FROM feedback_messages ORDER BY CASE WHEN status = 'new' THEN 0 ELSE 1 END, id DESC")
            feedback = [dict(r) for r in cur.fetchall()]

            conn.close()
            self.send_json({
                "settings": settings,
                "users": users,
                "forms": forms,
                "feedback": feedback,
                "verified_tenders": prozorro_service.VERIFIED_PROZORRO_TENDERS
            })
            return

        if path == "/api/feedback":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            conn = get_db()
            cur = conn.cursor()
            if user["role"] == "admin":
                cur.execute("SELECT * FROM feedback_messages ORDER BY CASE WHEN status = 'new' THEN 0 ELSE 1 END, id DESC")
            else:
                cur.execute(
                    "SELECT * FROM feedback_messages WHERE user_id = ? OR LOWER(sender_email) = LOWER(?) ORDER BY id DESC",
                    (user["id"], user["email"])
                )
            items = [dict(r) for r in cur.fetchall()]
            conn.close()
            self.send_json({"messages": items})
            return

        self.send_json({"error": "Маршрут не знайдено"}, 404)

    def do_POST(self):
        try:
            self._handle_POST()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_json({"error": f"Помилка сервера: {str(e)}"}, 500)

    def _handle_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.read_json_body()

        if path == "/api/auth/forgot-password":
            email = (body.get("email") or "").strip().lower()
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
            user = cur.fetchone()
            if user:
                token = secrets.token_urlsafe(32)
                now_dt = datetime.now()
                exp_dt = now_dt + timedelta(minutes=15)
                cur.execute("UPDATE password_resets SET is_used = 1 WHERE user_id = ?", (user["id"],))
                cur.execute("""
                    INSERT INTO password_resets (user_id, token, expires_at, is_used, created_at)
                    VALUES (?, ?, ?, 0, ?)
                """, (user["id"], token, exp_dt.strftime("%Y-%m-%d %H:%M:%S"), now_dt.strftime("%Y-%m-%d %H:%M:%S")))
                conn.commit()
            conn.close()
            # Розділ 2: Пункт 1 - Захист від розвідки (Anti-Enumeration) — єдиний нейтральний текст
            self.send_json({
                "ok": True,
                "message": "Якщо вказану адресу зареєстровано в системі, інструкції для відновлення доступу надіслано на вашу поштову скриньку."
            })
            return

        if path == "/api/auth/reset-password":
            token = (body.get("token") or "").strip()
            new_password = body.get("new_password") or ""
            if not token or len(new_password) < 6:
                self.send_json({"error": "Вкажіть дійсний токен відновлення та новий пароль (не менше 6 символів)."}, 400)
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM password_resets WHERE token = ? AND is_used = 0", (token,))
            reset_entry = cur.fetchone()
            if not reset_entry:
                conn.close()
                self.send_json({"error": "Токен відновлення не знайдено або він вже був використаний."}, 400)
                return
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if reset_entry["expires_at"] < now_str:
                cur.execute("UPDATE password_resets SET is_used = 1 WHERE id = ?", (reset_entry["id"],))
                conn.commit()
                conn.close()
                self.send_json({"error": "Термін дії посилання для відновлення (15 хвилин) вичерпано. Замовте нове посилання."}, 400)
                return
            
            # Оновлення пароля та одноразове погашення токена (Розділ 2, Пункт 2)
            cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), reset_entry["user_id"]))
            cur.execute("UPDATE password_resets SET is_used = 1 WHERE id = ?", (reset_entry["id"],))
            # Global logout: анулюємо старі сесії
            cur.execute("DELETE FROM sessions WHERE user_id = ?", (reset_entry["user_id"],))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "message": "Пароль успішно змінено! Тепер ви можете увійти до кабінету з новим паролем."})
            return

        if path == "/api/user/change-password":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            cur_pwd = body.get("current_password") or ""
            new_pwd = body.get("new_password") or ""
            if hash_password(cur_pwd) != user["password_hash"]:
                self.send_json({"error": "Поточний пароль введено невірно."}, 400)
                return
            if len(new_pwd) < 6:
                self.send_json({"error": "Новий пароль повинен містити щонайменше 6 символів."}, 400)
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_pwd), user["id"]))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "message": "Пароль успішно оновлено!"})
            return

        if path == "/api/auth/logout":
            auth = self.headers.get("Authorization", "")
            token = auth[7:].strip() if auth.startswith("Bearer ") else ""
            if token:
                SESSIONS.pop(token, None)
                conn = get_db()
                cur = conn.cursor()
                cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                conn.close()
            self.send_json({"ok": True})
            return

        if path == "/api/admin/auth/login":
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE LOWER(email) = ? AND password_hash = ?", (email, hash_password(password)))
            user = cur.fetchone()
            conn.close()
            if not user:
                self.send_json({"error": "Невірний email або пароль адміністратора"}, 401)
                return
            if user["role"] != "admin":
                self.send_json({"error": "Доступ заборонено: ваш обліковий запис не має прав адміністратора. Клієнти входять через головну сторінку."}, 403)
                return
            if not user["is_active"]:
                self.send_json({"error": "Обліковий запис адміністратора вимкнено"}, 403)
                return
            token = secrets.token_hex(24)
            SESSIONS[token] = user["id"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], now_str))
            conn.commit()
            conn.close()
            self.send_json({"token": token, "user": serialize_user(user)})
            return

        if path == "/api/auth/login":
            email = (body.get("email") or "").strip().lower()
            password = body.get("password") or ""
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE LOWER(email) = ? AND password_hash = ?", (email, hash_password(password)))
            user = cur.fetchone()
            conn.close()
            if not user:
                self.send_json({"error": "Невірний email або пароль"}, 401)
                return
            if user["role"] == "admin":
                self.send_json({"error": "Це вхід для клієнтів. Для входу в кабінет адміністратора перейдіть за адресою: /admin", "is_admin": True}, 403)
                return
            if not user["is_active"]:
                self.send_json({"error": "Обліковий запис вимкнено адміністратором"}, 403)
                return
            token = secrets.token_hex(24)
            SESSIONS[token] = user["id"]
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], now_str))
            conn.commit()
            conn.close()
            self.send_json({"token": token, "user": serialize_user(user)})
            return

        if path == "/api/auth/register":
            # Розділ 1: Пункт 1 - Honeypot
            honeypot = (body.get("honeypot") or "").strip()
            if honeypot:
                self.send_json({"error": "Виявлено автоматизований запит."}, 400)
                return

            # Розділ 1: Пункт 2 - Часовий бар'єр (мінімум 1 секунда на заповнення)
            form_duration_ms = body.get("form_duration_ms")
            if form_duration_ms is not None:
                try:
                    if float(form_duration_ms) < 1000:
                        self.send_json({"error": "Занадто швидка відправка форми (заповнення тривало менше 1 секунди). Будь ласка, перевірте дані."}, 400)
                        return
                except (ValueError, TypeError):
                    pass

            email = (body.get("email") or "").strip().lower()

            # Розділ 1: Пункт 3 - Блокування одноразових/тимчасових поштових скриньок
            email_domain = email.split("@")[-1].lower().strip() if "@" in email else ""
            if email_domain in DISPOSABLE_EMAIL_DOMAINS:
                self.send_json({"error": "Реєстрація з використанням тимчасових та одноразових скриньок заборонена. Будь ласка, вкажіть офіційний або робочий email."}, 400)
                return

            # Розділ 1: Пункт 5 - Обмеження частоти реєстрацій з однієї IP-адреси (максимум 3 на годину)
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            now_time = time.time()
            if client_ip not in ("127.0.0.1", "::1", "localhost"):
                recent_attempts = [ts for ts in REGISTRATION_IP_HISTORY.get(client_ip, []) if now_time - ts < 3600]
                if len(recent_attempts) >= 5:
                    self.send_json({"error": "Перевищено ліміт реєстрацій з вашої IP-адреси (максимум 5 на годину). Спробуйте пізніше."}, 429)
                    return
                recent_attempts.append(now_time)
                REGISTRATION_IP_HISTORY[client_ip] = recent_attempts
            password = body.get("password") or ""
            full_name = (body.get("full_name") or "").strip()
            org_name = (body.get("org_name") or "").strip()
            edrpou = (body.get("edrpou") or "").strip()
            phone = (body.get("phone") or "").strip()
            address = (body.get("address") or "").strip()
            director_name = (body.get("director_name") or "").strip()
            director_title = (body.get("director_title") or "").strip()
            website = (body.get("website") or "").strip()
            account_type = (body.get("account_type") or "buyer").strip()

            if not email or not password or not full_name:
                self.send_json({"error": "Заповніть обов'язкові поля: ПІБ, Email та пароль"}, 400)
                return

            conn = get_db()
            cur = conn.cursor()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                perms_str = json.dumps(DEFAULT_USER_PERMISSIONS, ensure_ascii=False)
                cur.execute("""
                    INSERT INTO users (email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', ?, 'manual', 5, 1, ?, ?)
                """, (email, hash_password(password), full_name, org_name, edrpou, phone, address, director_name, director_title, website, account_type, perms_str, now_str))
                uid = cur.lastrowid
                conn.commit()
            except sqlite3.IntegrityError:
                conn.close()
                self.send_json({"error": "Користувач з таким Email вже зареєстрований"}, 400)
                return

            cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
            user = cur.fetchone()
            conn.close()
            token = secrets.token_hex(24)
            SESSIONS[token] = user["id"]
            self.send_json({"token": token, "user": serialize_user(user)})
            return

        if path == "/api/profile/update":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            perms = parse_permissions(user["permissions_json"])
            can_edit_org = (user["role"] == "admin") or bool(perms.get("can_edit_org_details", False))
            new_org_name = (body.get("org_name") if ("org_name" in body and can_edit_org) else user["org_name"])
            new_edrpou = (body.get("edrpou") if ("edrpou" in body and can_edit_org) else user["edrpou"])
            # Після збереження реквізитів поля назви та ЄДРПОУ знову стають неактивними для клієнта
            if user["role"] != "admin":
                perms["can_edit_org_details"] = False
            auth_persons_list = parse_authorized_persons(
                body.get("authorized_persons") if "authorized_persons" in body else user["authorized_persons_json"]
            )
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE users
                SET full_name = ?, org_name = ?, edrpou = ?, phone = ?, address = ?, director_name = ?, director_title = ?, website = ?, authorized_persons_json = ?, permissions_json = ?
                WHERE id = ?
            """, (
                body.get("full_name") or user["full_name"],
                new_org_name,
                new_edrpou,
                body.get("phone") if "phone" in body else user["phone"],
                body.get("address") if "address" in body else user["address"],
                body.get("director_name") if "director_name" in body else user["director_name"],
                body.get("director_title") if "director_title" in body else user["director_title"],
                body.get("website") if "website" in body else user["website"],
                json.dumps(auth_persons_list, ensure_ascii=False),
                json.dumps(perms, ensure_ascii=False),
                user["id"]
            ))
            conn.commit()
            cur.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
            updated = serialize_user(cur.fetchone())
            conn.close()
            self.send_json({"user": updated})
            return

        if path == "/api/profile/authorized-persons":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            action = (body.get("action") or "").strip().lower()
            person_name = (body.get("name") or "").strip()
            current_list = parse_authorized_persons(user["authorized_persons_json"])
            if action == "add":
                if not person_name:
                    self.send_json({"error": "Введіть ПІБ уповноваженої особи"}, 400)
                    return
                if person_name not in current_list:
                    current_list.append(person_name)
            elif action == "delete":
                idx = body.get("index")
                if idx is not None and isinstance(idx, int) and 0 <= idx < len(current_list):
                    current_list.pop(idx)
                elif person_name in current_list:
                    current_list.remove(person_name)
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET authorized_persons_json = ? WHERE id = ?",
                (json.dumps(current_list, ensure_ascii=False), user["id"])
            )
            conn.commit()
            cur.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
            updated = serialize_user(cur.fetchone())
            conn.close()
            self.send_json({"user": updated})
            return

        if path == "/api/feedback/send":
            user = self.get_current_user()
            subject = (body.get("subject") or "Звернення до адміністратора").strip()
            message = (body.get("message") or "").strip()
            if not message:
                self.send_json({"error": "Введіть текст повідомлення для адміністратора"}, 400)
                return
            if user:
                uid = user["id"]
                s_name = user["full_name"]
                s_email = user["email"]
                s_org = user["org_name"] or ""
                s_edrpou = user["edrpou"] or ""
            else:
                uid = 0
                s_name = (body.get("sender_name") or "").strip()
                s_email = (body.get("sender_email") or "").strip()
                s_org = (body.get("sender_org") or "").strip()
                s_edrpou = (body.get("sender_edrpou") or "").strip()
                if not s_name or not s_email:
                    self.send_json({"error": "Вкажіть ваше ім'я та контактний Email або телефон"}, 400)
                    return
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO feedback_messages (
                    user_id, sender_name, sender_email, sender_org, sender_edrpou,
                    subject, message, admin_reply, status, created_at, replied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '', 'new', ?, '')
            """, (uid, s_name, s_email, s_org, s_edrpou, subject, message, now_str))
            msg_id = cur.lastrowid
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "id": msg_id})
            return

        if path == "/api/forms/parse-filled-docx":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            if user["role"] != "admin":
                perms = parse_permissions(user["permissions_json"])
                if not perms.get("can_docx_upload", True):
                    self.send_json({"error": "Завантаження .docx форм вимкнено для вашого рівня доступу."}, 403)
                    return
            filename = body.get("filename") or "filled_form.docx"
            b64 = body.get("content_base64") or ""
            if not b64:
                self.send_json({"error": "Порожній файл"}, 400)
                return
            safe_name = f"user_{user['id']}_{int(datetime.now().timestamp())}_{os.path.basename(filename)}"
            save_path = os.path.join(USER_UPLOADS_DIR, safe_name)
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64))
            try:
                parsed_vals = doc_generator.parse_filled_docx_values(save_path)
                self.send_json({"saved_name": safe_name, "parsed": parsed_vals})
            except Exception as e:
                self.send_json({"error": f"Не вдалося прочитати таблицю .docx: {e}"}, 400)
            return

        if path == "/api/orders/preview-benchmarks":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            input_data = body.get("input_data") or {}
            custom_benchmarks = body.get("custom_benchmarks")
            benchmarks = prozorro_service.find_benchmarks_for_order(input_data, custom_benchmarks)
            for b in benchmarks:
                if not b.get("prozorro_url") and b.get("tender_id"):
                    b["prozorro_url"] = f"https://prozorro.gov.ua/tender/{b['tender_id']}"

            unit_prices = [float(b.get("unit_price_no_vat") or 0) for b in benchmarks if float(b.get("unit_price_no_vat") or 0) > 0]
            avg_p = sum(unit_prices) / len(unit_prices) if unit_prices else 0.0
            min_p = min(unit_prices) if unit_prices else 0.0
            max_p = max(unit_prices) if unit_prices else 0.0

            cust_unit = float(input_data.get("unit_price_no_vat") or 0.0)
            if cust_unit <= 0:
                ev = float(input_data.get("expected_value") or 0.0)
                qty = float(input_data.get("quantity") or 0.0)
                if ev > 0 and qty > 0:
                    cust_unit = ev / qty

            is_highest = False
            if benchmarks and cust_unit > 0:
                has_higher = any(float(b.get("unit_price_no_vat") or 0) > cust_unit for b in benchmarks)
                if not has_higher:
                    is_highest = True

            stats = {
                "avg_unit_price": round(avg_p, 2),
                "min_unit_price": round(min_p, 2),
                "max_unit_price": round(max_p, 2),
                "is_expected_value_highest": is_highest
            }
            self.send_json({"ok": True, "benchmarks": benchmarks, "stats": stats})
            return

        if path == "/api/orders/create":
            user = self.get_current_user()
            if not user:
                self.send_json({"error": "Не авторизовано"}, 401)
                return
            perms = parse_permissions(user["permissions_json"])
            if user["role"] != "admin" and not perms.get("can_create_orders", True):
                self.send_json({"error": "Подача нових заявок не передбачена вашим ступенем доступу до функціоналу."}, 403)
                return
            if user["quota"] <= 0 and user["role"] != "admin":
                self.send_json({"error": "Вичерпано ліміт доступних замовлень у кабінеті. Зверніться до адміністратора."}, 403)
                return

            form_id = int(body.get("form_id") or 1)
            input_data = body.get("input_data") or {}
            uploaded_docx_name = body.get("uploaded_docx_name") or ""
            custom_benchmarks = body.get("custom_benchmarks")

            can_edit_org = (user["role"] == "admin") or bool(perms.get("can_edit_org_details", False))
            if (not can_edit_org or not input_data.get("buyer_name")) and user["org_name"]:
                input_data["buyer_name"] = user["org_name"]
            if (not can_edit_org or not input_data.get("edrpou")) and user["edrpou"]:
                input_data["edrpou"] = user["edrpou"]
            if not input_data.get("buyer_address") and user["address"]:
                input_data["buyer_address"] = user["address"]
            if not input_data.get("director_name") and user["director_name"]:
                input_data["director_name"] = user["director_name"]
            if not input_data.get("director_title") and user["director_title"]:
                input_data["director_title"] = user["director_title"]
            if not input_data.get("authorized_person") and user["full_name"]:
                input_data["authorized_person"] = user["full_name"]
            input_data.pop("email", None)
            if not input_data.get("phone") and user["phone"]:
                input_data["phone"] = user["phone"]
            if not input_data.get("website") and user["website"]:
                input_data["website"] = user["website"]

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM forms WHERE id = ?", (form_id,))
            form_row = cur.fetchone()
            form_title = form_row["title"] if form_row else "Форма заявки"

            is_rel = should_auto_release(conn, user)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            benchmarks = prozorro_service.find_benchmarks_for_order(input_data, custom_benchmarks)
            for b in benchmarks:
                if not b.get("prozorro_url") and b.get("tender_id"):
                    b["prozorro_url"] = f"https://prozorro.gov.ua/tender/{b['tender_id']}"

            cur.execute("""
                INSERT INTO orders (
                    user_id, form_id, form_title, is_released, payment_status,
                    input_data_json, benchmarks_json, stats_json, consultation_json,
                    uploaded_docx_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'unpaid', '{}', '[]', '{}', '{}', ?, ?, ?)
            """, (user["id"], form_id, form_title, is_rel, uploaded_docx_name, now_str, now_str))
            order_id = cur.lastrowid

            order_folder = os.path.join(ORDERS_RESULT_DIR, f"order_{order_id}")
            gen_res = doc_generator.generate_justification_bundle(input_data, benchmarks, order_folder)
            consult = prozorro_service.generate_three_variant_consultation(input_data, gen_res["stats"], benchmarks)

            cur.execute("""
                UPDATE orders
                SET input_data_json = ?, benchmarks_json = ?, stats_json = ?, consultation_json = ?,
                    file1_name = ?, file1_path = ?, file2_name = ?, file2_path = ?
                WHERE id = ?
            """, (
                json.dumps(input_data, ensure_ascii=False),
                json.dumps(benchmarks, ensure_ascii=False),
                json.dumps(gen_res["stats"], ensure_ascii=False),
                json.dumps(consult, ensure_ascii=False),
                gen_res["file1_name"],
                gen_res["file1_path"],
                gen_res["file2_name"],
                gen_res["file2_path"],
                order_id
            ))

            if user["role"] != "admin":
                cur.execute("UPDATE users SET quota = CASE WHEN quota > 0 THEN quota - 1 ELSE 0 END WHERE id = ?", (user["id"],))

            conn.commit()
            conn.close()
            self.send_json({"order_id": order_id, "is_released": bool(is_rel)})
            return

        # ==================== АДМІН-ПАНЕЛЬ API ====================
        user = self.get_current_user()
        if not user or user["role"] != "admin":
            self.send_json({"error": "Доступ дозволено виключно адміністратору (Артему)"}, 403)
            return

        if path == "/api/admin/settings":
            conn = get_db()
            cur = conn.cursor()
            for k in ["delivery_mode", "service_title", "platform_name", "platform_subtitle", "logo_data_url", "contact_email", "contact_phone"]:
                if k in body:
                    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(body[k])))
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        if path == "/api/admin/orders/delete":
            oid = int(body.get("id") or 0)
            if not oid:
                self.send_json({"error": "Не вказано ID заявки"}, 400)
                return
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM orders WHERE id = ?", (oid,))
            conn.commit()
            conn.close()
            folder = os.path.join(ORDERS_RESULT_DIR, f"order_{oid}")
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                except Exception:
                    pass
            self.send_json({"ok": True, "id": oid})
            return

        if path == "/api/admin/orders/toggle-release":
            order_id = int(body.get("order_id") or 0)
            is_released = 1 if body.get("is_released") else 0
            admin_comment = body.get("admin_comment")
            conn = get_db()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if admin_comment is not None:
                cur.execute("UPDATE orders SET is_released = ?, admin_comment = ?, updated_at = ? WHERE id = ?", (is_released, admin_comment, now_str, order_id))
            else:
                cur.execute("UPDATE orders SET is_released = ?, updated_at = ? WHERE id = ?", (is_released, now_str, order_id))

            # Автоматичне надсилання сповіщення клієнту при погодженні заявки
            if is_released == 1:
                cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
                ord_row = cur.fetchone()
                if ord_row:
                    uid = ord_row["user_id"]
                    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
                    u_row = cur.fetchone()
                    u_name = u_row["full_name"] if u_row else "Замовник"
                    u_email = u_row["email"] if u_row else ""
                    u_org = u_row["org_name"] if u_row else ""
                    u_edrpou = u_row["edrpou"] if u_row else ""

                    inp = json.loads(ord_row["input_data_json"] or "{}")
                    subj = inp.get("subject_name", "предмет закупівлі")
                    fb_subject = f"Погодження заявки: {subj}"
                    fb_message = f"Заявку щодо закупівлі «{subj}» успішно перевірено та погоджено адміністратором платформи."
                    admin_reply = f"Доступ відкрито! Готові файли Обґрунтування та Додатка до обґрунтування доступні для завантаження у вашому кабінеті у вкладці «Мої заявки та Результати»."
                    cur.execute("""
                        INSERT INTO feedback_messages (
                            user_id, sender_name, sender_email, sender_org, sender_edrpou,
                            subject, message, admin_reply, status, created_at, replied_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'replied', ?, ?)
                    """, (uid, u_name, u_email, u_org, u_edrpou, fb_subject, fb_message, admin_reply, now_str, now_str))

            conn.commit()
            conn.close()
            self.send_json({"ok": True, "order_id": order_id, "is_released": is_released})
            return

        if path == "/api/admin/orders/regenerate":
            order_id = int(body.get("order_id") or 0)
            new_input = body.get("input_data")
            new_benchmarks = body.get("benchmarks")
            admin_comment = body.get("admin_comment", "")
            is_released = body.get("is_released")

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.close()
                self.send_json({"error": "Заявку не знайдено"}, 404)
                return

            inp = new_input if isinstance(new_input, dict) else json.loads(order["input_data_json"])
            bench = new_benchmarks if isinstance(new_benchmarks, list) else json.loads(order["benchmarks_json"])
            order_folder = os.path.join(ORDERS_RESULT_DIR, f"order_{order_id}")
            gen_res = doc_generator.generate_justification_bundle(inp, bench, order_folder)
            consult = prozorro_service.generate_three_variant_consultation(inp, gen_res["stats"], bench)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            rel_val = int(bool(is_released)) if is_released is not None else order["is_released"]

            cur.execute("""
                UPDATE orders
                SET input_data_json = ?, benchmarks_json = ?, stats_json = ?, consultation_json = ?,
                    file1_name = ?, file1_path = ?, file2_name = ?, file2_path = ?,
                    admin_comment = ?, is_released = ?, updated_at = ?
                WHERE id = ?
            """, (
                json.dumps(inp, ensure_ascii=False),
                json.dumps(bench, ensure_ascii=False),
                json.dumps(gen_res["stats"], ensure_ascii=False),
                json.dumps(consult, ensure_ascii=False),
                gen_res["file1_name"],
                gen_res["file1_path"],
                gen_res["file2_name"],
                gen_res["file2_path"],
                admin_comment,
                rel_val,
                now_str,
                order_id
            ))
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        if path == "/api/admin/users/create":
            email = (body.get("email") or "").strip().lower()
            password = (body.get("password") or "").strip()
            full_name = (body.get("full_name") or "").strip()
            org_name = (body.get("org_name") or "").strip()
            edrpou = (body.get("edrpou") or "").strip()
            phone = (body.get("phone") or "").strip()
            address = (body.get("address") or "").strip()
            director_name = (body.get("director_name") or "").strip()
            director_title = (body.get("director_title") or "").strip()
            website = (body.get("website") or "").strip()
            role = body.get("role") if body.get("role") in ("user", "admin") else "user"
            account_type = body.get("account_type") if body.get("account_type") in ("client", "user", "admin") else ("admin" if role == "admin" else "user")
            if account_type == "admin":
                role = "admin"
            delivery_override = body.get("delivery_override") or "default"
            quota = int(body.get("quota", 5))
            is_active = 1 if body.get("is_active", True) else 0
            perms = parse_permissions(body.get("permissions"))

            if not email or not password or not full_name:
                self.send_json({"error": "Вкажіть обов'язкові поля: ПІБ, Email та пароль користувача"}, 400)
                return

            conn = get_db()
            cur = conn.cursor()
            try:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("""
                    INSERT INTO users (
                        email, password_hash, full_name, org_name, edrpou, phone, address,
                        director_name, director_title, website, role, account_type, delivery_override,
                        quota, is_active, permissions_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email, hash_password(password), full_name, org_name, edrpou, phone, address,
                    director_name, director_title, website, role, account_type, delivery_override,
                    quota, is_active, json.dumps(perms, ensure_ascii=False), now_str
                ))
                new_uid = cur.lastrowid
                conn.commit()
            except sqlite3.IntegrityError:
                conn.close()
                self.send_json({"error": "Користувач з таким Email вже існує в базі"}, 400)
                return
            conn.close()
            self.send_json({"ok": True, "user_id": new_uid})
            return

        if path == "/api/admin/users/adjust-quota":
            uid = int(body.get("user_id") or 0)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, quota FROM users WHERE id = ?", (uid,))
            row = cur.fetchone()
            if not row:
                conn.close()
                self.send_json({"error": "Користувача не знайдено"}, 404)
                return
            if "new_quota" in body and body["new_quota"] is not None:
                new_q = max(0, int(body["new_quota"]))
            else:
                delta = int(body.get("delta") or 0)
                new_q = max(0, int(row["quota"]) + delta)
            cur.execute("UPDATE users SET quota = ? WHERE id = ?", (new_q, uid))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "user_id": uid, "quota": new_q})
            return

        if path == "/api/admin/users/update":
            uid = int(body.get("user_id") or 0)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE id = ?", (uid,))
            existing = cur.fetchone()
            if not existing:
                conn.close()
                self.send_json({"error": "Користувача не знайдено"}, 404)
                return

            full_name = (body.get("full_name") or existing["full_name"]).strip()
            email = (body.get("email") or existing["email"]).strip().lower()
            org_name = body.get("org_name") if "org_name" in body else existing["org_name"]
            edrpou = body.get("edrpou") if "edrpou" in body else existing["edrpou"]
            phone = body.get("phone") if "phone" in body else existing["phone"]
            address = body.get("address") if "address" in body else existing["address"]
            director_name = body.get("director_name") if "director_name" in body else existing["director_name"]
            director_title = body.get("director_title") if "director_title" in body else existing["director_title"]
            website = body.get("website") if "website" in body else existing["website"]
            role = body.get("role") if body.get("role") in ("user", "admin") else existing["role"]
            existing_acc_type = existing["account_type"] if "account_type" in existing.keys() else ("admin" if role == "admin" else "user")
            account_type = body.get("account_type") if body.get("account_type") in ("client", "user", "admin") else existing_acc_type
            if account_type == "admin":
                role = "admin"
            elif role == "admin" and body.get("account_type") in ("client", "user"):
                role = "user"
            quota = int(body.get("quota", existing["quota"]))
            delivery_override = body.get("delivery_override", existing["delivery_override"])
            is_active = 1 if body.get("is_active", bool(existing["is_active"])) else 0

            current_perms = parse_permissions(existing["permissions_json"])
            if "permissions" in body and isinstance(body["permissions"], dict):
                current_perms.update(body["permissions"])

            new_pw = (body.get("new_password") or "").strip()
            pw_hash = hash_password(new_pw) if new_pw else existing["password_hash"]

            auth_persons_list = parse_authorized_persons(
                body.get("authorized_persons") if "authorized_persons" in body else existing["authorized_persons_json"]
            )

            cur.execute("""
                UPDATE users
                SET email = ?, password_hash = ?, full_name = ?, org_name = ?, edrpou = ?, phone = ?, address = ?,
                    director_name = ?, director_title = ?, website = ?, role = ?, account_type = ?,
                    quota = ?, delivery_override = ?, is_active = ?, permissions_json = ?, authorized_persons_json = ?
                WHERE id = ?
            """, (
                email, pw_hash, full_name, org_name, edrpou, phone, address,
                director_name, director_title, website, role, account_type,
                quota, delivery_override, is_active, json.dumps(current_perms, ensure_ascii=False),
                json.dumps(auth_persons_list, ensure_ascii=False), uid
            ))
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        if path == "/api/admin/users/toggle-org-edit":
            uid = int(body.get("user_id") or 0)
            allow = bool(body.get("allow", False))
            fb_id = int(body.get("feedback_id") or 0)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, permissions_json FROM users WHERE id = ?", (uid,))
            existing = cur.fetchone()
            if not existing:
                conn.close()
                self.send_json({"error": "Користувача не знайдено"}, 404)
                return
            current_perms = parse_permissions(existing["permissions_json"])
            current_perms["can_edit_org_details"] = allow
            cur.execute(
                "UPDATE users SET permissions_json = ? WHERE id = ?",
                (json.dumps(current_perms, ensure_ascii=False), uid)
            )
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if fb_id and allow:
                cur.execute("""
                    UPDATE feedback_messages
                    SET status = 'replied',
                        admin_reply = CASE WHEN admin_reply IS NULL OR admin_reply = '' THEN 'Адміністратор надав дозвіл на зміну найменування та коду ЄДРПОУ.' ELSE admin_reply END,
                        replied_at = ?
                    WHERE id = ?
                """, (now_str, fb_id))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "user_id": uid, "can_edit_org_details": allow, "feedback_id": fb_id})
            return

        if path == "/api/admin/users/set-delivery-mode":
            uid = int(body.get("user_id") or 0)
            mode = (body.get("delivery_override") or "manual").strip().lower()
            if mode not in ("manual", "auto"):
                mode = "manual"
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE users SET delivery_override = ? WHERE id = ?", (mode, uid))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "user_id": uid, "delivery_override": mode})
            return

        if path == "/api/admin/feedback/reply":
            mid = int(body.get("message_id") or 0)
            reply_text = (body.get("admin_reply") or "").strip()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                UPDATE feedback_messages
                SET admin_reply = ?, status = 'replied', replied_at = ?
                WHERE id = ?
            """, (reply_text, now_str, mid))
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "id": mid})
            return

        if path == "/api/admin/feedback/delete":
            mid = int(body.get("message_id") or 0)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM feedback_messages WHERE id = ?", (mid,))
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        if path == "/api/admin/users/delete":
            uid = int(body.get("user_id") or 0)
            delete_orders = bool(body.get("delete_orders", True))
            if uid == user["id"]:
                self.send_json({"error": "Неможливо видалити власний обліковий запис адміністратора"}, 400)
                return
            conn = get_db()
            cur = conn.cursor()
            if delete_orders:
                cur.execute("DELETE FROM orders WHERE user_id = ?", (uid,))
            cur.execute("DELETE FROM users WHERE id = ?", (uid,))
            conn.commit()
            conn.close()
            # Очищаємо активні сесії видаленого користувача
            tokens_to_remove = [t for t, u_id in SESSIONS.items() if u_id == uid]
            for t in tokens_to_remove:
                SESSIONS.pop(t, None)
            self.send_json({"ok": True})
            return

        if path == "/api/admin/forms/upload-docx":
            filename = body.get("filename") or "uploaded_form.docx"
            b64 = body.get("content_base64") or ""
            custom_title = (body.get("title") or "").strip()
            custom_desc = (body.get("description") or "").strip()
            if not b64:
                self.send_json({"error": "Не вибрано файл .docx"}, 400)
                return

            safe_name = f"admin_form_{int(datetime.now().timestamp())}_{os.path.basename(filename)}"
            save_path = os.path.join(FORMS_UPLOAD_DIR, safe_name)
            with open(save_path, "wb") as f:
                f.write(base64.b64decode(b64))

            parsed_struct = doc_generator.parse_docx_form_structure(save_path)
            fields = parsed_struct["fields"]
            existing_keys = {f["key"] for f in fields}
            if "subject_name" not in existing_keys:
                fields.append({"key": "subject_name", "label": "Конкретна назва предмета закупівлі", "type": "text", "required": True})
            if "expected_value" not in existing_keys:
                fields.append({"key": "expected_value", "label": "Очікувана вартість предмета закупівлі (без ПДВ, грн)", "type": "number", "required": True})
            if "quantity" not in existing_keys:
                fields.append({"key": "quantity", "label": "Кількість (обсяг закупівлі)", "type": "number", "required": True})
            if "unit_name" not in existing_keys:
                fields.append({"key": "unit_name", "label": "Одиниця виміру", "type": "text", "required": True})

            final_title = custom_title or parsed_struct["title"]
            final_desc = custom_desc or f"Імпортовано з файлу {filename} через адмін-панель."

            doc_generator.generate_form_template_docx(final_title, fields, save_path)

            conn = get_db()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
                INSERT INTO forms (title, description, fields_json, docx_template_path, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (final_title, final_desc, json.dumps(fields, ensure_ascii=False), save_path, now_str))
            fid = cur.lastrowid
            conn.commit()
            conn.close()
            self.send_json({"ok": True, "form_id": fid, "title": final_title, "fields": fields})
            return

        if path == "/api/admin/forms/save":
            fid = body.get("id")
            title = (body.get("title") or "Нова форма закупівлі").strip()
            description = (body.get("description") or "").strip()
            fields = [
                fl for fl in (body.get("fields") or [])
                if fl.get("key") != "email"
                and "email" not in str(fl.get("label", "")).lower()
                and "електронна пошта" not in str(fl.get("label", "")).lower()
            ]
            is_active = 1 if body.get("is_active", True) else 0
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conn = get_db()
            cur = conn.cursor()
            if fid:
                tpath = os.path.join(FORMS_UPLOAD_DIR, f"Форма_{fid}_оновлена.docx")
                doc_generator.generate_form_template_docx(title, fields, tpath)
                cur.execute("""
                    UPDATE forms
                    SET title = ?, description = ?, fields_json = ?, docx_template_path = ?, is_active = ?
                    WHERE id = ?
                """, (title, description, json.dumps(fields, ensure_ascii=False), tpath, is_active, int(fid)))
            else:
                tpath = os.path.join(FORMS_UPLOAD_DIR, f"Форма_{int(datetime.now().timestamp())}.docx")
                doc_generator.generate_form_template_docx(title, fields, tpath)
                cur.execute("""
                    INSERT INTO forms (title, description, fields_json, docx_template_path, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (title, description, json.dumps(fields, ensure_ascii=False), tpath, is_active, now_str))
            conn.commit()
            conn.close()
            self.send_json({"ok": True})
            return

        self.send_json({"error": "Невідома дія"}, 404)


def run_server(port=8080):
    init_db()
    port = int(os.environ.get("PORT", port))
    host = "0.0.0.0"
    server = ThreadingHTTPServer((host, port), TenderAppHandler)
    print(f"============================================================")
    print(f" ТЕНДЕРНИЙ ПОМІЧНИК — СЕРВЕР ЗАПУЩЕНО")
    print(f" URL: http://127.0.0.1:{port}")
    print(f" Адміністратор: artemvolodymyrovych@gmail.com")
    print(f"============================================================")
    server.serve_forever()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(p)
