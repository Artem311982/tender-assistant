import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory", "tender_assistant.db")
SQL_OUT = os.path.join(r"C:\Projects\Тендерний помічник", "supabase_initial_data.sql")

def generate_export_sql():
    if not os.path.exists(DB_PATH):
        print("Базу не знайдено:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    lines = ["-- АВТОМАТИЧНИЙ ЕКСПОРТ ДАНИХ З ЛОКАЛЬНОЇ БАЗИ ДО SUPABASE\n"]

    # 1. Settings
    cur.execute("SELECT key, value FROM settings")
    rows = cur.fetchall()
    lines.append("-- Налаштування")
    for r in rows:
        val = r["value"].replace("'", "''")
        lines.append(f"INSERT INTO settings (key, value) VALUES ('{r['key']}', '{val}') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;")

    # 2. Users
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    lines.append("\n-- Користувачі та Клієнти")
    for r in rows:
        fn = (r["full_name"] or "").replace("'", "''")
        org = (r["org_name"] or "").replace("'", "''")
        addr = (r["address"] or "").replace("'", "''")
        d_name = (r["director_name"] or "").replace("'", "''")
        d_title = (r["director_title"] or "").replace("'", "''")
        perms = (r["permissions_json"] or "{}").replace("'", "''")
        lines.append(
            f"INSERT INTO users (id, email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, created_at) "
            f"VALUES ({r['id']}, '{r['email']}', '{r['password_hash']}', '{fn}', '{org}', '{r['edrpou']}', '{r['phone']}', '{addr}', '{d_name}', '{d_title}', '{r['website']}', '{r['role']}', '{r['account_type']}', '{r['delivery_override']}', {r['quota']}, {r['is_active']}, '{perms}', '{r['created_at']}') "
            f"ON CONFLICT (email) DO NOTHING;"
        )

    # 3. Forms
    cur.execute("SELECT * FROM forms")
    rows = cur.fetchall()
    lines.append("\n-- Форми")
    for r in rows:
        t = (r["title"] or "").replace("'", "''")
        desc = (r["description"] or "").replace("'", "''")
        fj = (r["fields_json"] or "[]").replace("'", "''")
        lines.append(f"INSERT INTO forms (id, title, description, fields_json, is_active, created_at) VALUES ({r['id']}, '{t}', '{desc}', '{fj}', {r['is_active']}, '{r['created_at']}');")

    conn.close()

    with open(SQL_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("SUCCESS! Створено SQL-файл експорту:", SQL_OUT)

if __name__ == "__main__":
    generate_export_sql()
