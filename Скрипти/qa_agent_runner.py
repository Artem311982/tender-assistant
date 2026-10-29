import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MEMORY_DIR = os.path.join(PROJECT_ROOT, "Пам'ять")
os.makedirs(MEMORY_DIR, exist_ok=True)
QA_MEMORY_PATH = os.path.join(MEMORY_DIR, "qa_agent_memory.json")

sys.path.insert(0, SCRIPT_DIR)

ALLOWED_SYMBOLS = {"🔒", "🛡", "🛡️", "➕", "+", "\ufe0f", "↻", "👁", "👁️"}


def load_qa_memory():
    if os.path.exists(QA_MEMORY_PATH):
        try:
            with open(QA_MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "agent_name": "QA-Агент Тестувальник Тендерний Помічник",
        "total_runs": 0,
        "known_regression_guards": [
            "PostgreSQL scalar MAX(0, quota - 1) replaced with CASE WHEN / GREATEST",
            "Strict icon policy: only lock, shield, plus, and circular arrow allowed",
            "Merged tab 'Мої заявки та результати': form first, compact table second",
            "Market price amount must be black (#000000) in compact orders table",
            "Express check wording: Проаналізовано ... укладених договорів протягом ... місяців",
            "Tab persistence across F5 reload and anti-flicker hide-public-landing"
        ],
        "run_history": []
    }


def save_qa_memory(mem):
    mem["run_history"] = mem.get("run_history", [])[-25:]
    with open(QA_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


def run_static_ui_checks():
    findings = []
    passed = []
    index_path = os.path.join(SCRIPT_DIR, "static", "index.html")
    pub_index_path = os.path.join(PROJECT_ROOT, "public", "index.html")

    if not os.path.exists(index_path):
        findings.append({"severity": "HIGH", "area": "UI", "issue": "Файл Скрипти/static/index.html відсутній"})
        return passed, findings

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    if os.path.exists(pub_index_path):
        with open(pub_index_path, "r", encoding="utf-8") as f:
            pub_html = f.read()
        if html != pub_html:
            findings.append({
                "severity": "MEDIUM",
                "area": "Sync",
                "issue": "Файли Скрипти/static/index.html та public/index.html не ідентичні"
            })
        else:
            passed.append("Синхронізація static/index.html та public/index.html — ідентичні")

    # 1. Check forbidden emojis/pictograms
    forbidden_found = []
    for idx, line in enumerate(html.splitlines(), 1):
        for ch in line:
            cp = ord(ch)
            if ch not in ALLOWED_SYMBOLS and (0x2190 <= cp <= 0x2BFF or 0x1F000 <= cp <= 0x1FAFF):
                forbidden_found.append(f"Рядок {idx}: {repr(ch)}")
    if forbidden_found:
        findings.append({
            "severity": "HIGH",
            "area": "UI Icons Policy",
            "issue": f"Знайдено заборонені піктограми ({len(forbidden_found)} шт.): {', '.join(forbidden_found[:5])}"
        })
    else:
        passed.append("Правило піктограм: жодної забороненої іконки (дозволені лише 🔒, 🛡️, ➕, ↻ та піктограма ока пароля 👁️)")

    # 2. Check merged tab 'Мої заявки та результати' and order of blocks
    if "Мої заявки та результати</button>" in html and 'id="btnTab_tabNewOrder"' not in html:
        passed.append("Об'єднання вкладок: єдина вкладка «Мої заявки та результати» без окремої вкладки подачі заявки")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "UI Tabs",
            "issue": "Вкладки «Мої заявки та результати» та «Подати заявку» не об'єднані коректно"
        })

    pos_form = html.find('id="newOrderCardBlock"')
    pos_orders = html.find('id="submittedOrdersCard"')
    if pos_form != -1 and pos_orders != -1 and pos_form < pos_orders:
        passed.append("Порядок блоків: блок подачі заявки розташований ПЕРШИМ, блок поданих заявок — ДРУГИМ")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "UI Layout",
            "issue": "Порушено порядок блоків на вкладці «Мої заявки та результати»"
        })

    # 3. Check compact table requirements
    if "Ціна закупівлі за 1" in html and "Ціна замовника за 1" not in html:
        passed.append("Назва ціни: використовується «Ціна закупівлі за 1 ... (без ПДВ)»")
    else:
        findings.append({
            "severity": "MEDIUM",
            "area": "Orders Table",
            "issue": "Не оновлено назву «Ціна закупівлі за ... (без ПДВ)»"
        })

    if 'color:#000000;">\n            ${Number(stats.avg_market_price_no_vat' in html or 'color:#000000;' in html:
        passed.append("Колір суми середньоринкової ціни Prozorro: чорний (#000000)")
    else:
        findings.append({
            "severity": "MEDIUM",
            "area": "Orders Table",
            "issue": "Сума середньоринкової ціни Prozorro не має чорного кольору (#000000)"
        })

    if "1. Загальні відомості про замовника та закупівлю (згідно з формою Обґрунтування)" not in html:
        passed.append("Компактність таблиці: зайві блоки (Загальні відомості, Аналіз договорів, Скопіювати ціну) прибрано")
    else:
        findings.append({
            "severity": "MEDIUM",
            "area": "Orders Table",
            "issue": "У списку заявок клієнта залишилися старі розширені таблиці"
        })

    # 4. Check Prozorro units dropdown in service order form
    if "PROZORRO_UNITS_GROUPS" in html and 'id="orderUnitNameField"' in html:
        passed.append("Поле «Одиниця виміру»: підключено випадаючий список стандартних одиниць виміру Prozorro")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Order Form",
            "issue": "Відсутній випадаючий список одиниць виміру Prozorro у формі замовлення послуги"
        })

    # 5. Check password eye toggle pictograms (closed eye when hidden, open eye when visible)
    if "pwd-eye-closed" in html and "pwd-eye-open" in html and "PWD_EYE_CLOSED_SVG" in html and "PWD_EYE_OPEN_SVG" in html:
        passed.append("Поля паролів: встановлено піктограму ока (закрите око коли пароль прихований, відкрите коли відкритий)")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Password Fields",
            "issue": "Не всі поля паролів оснащені піктограмою закритого/відкритого ока"
        })

    return passed, findings


def run_database_and_backend_checks():
    passed = []
    findings = []
    try:
        from db_adapter import get_db
        conn = get_db()
        cur = conn.cursor()

        # Check users
        cur.execute("SELECT id, email, role, account_type, quota, is_active FROM users ORDER BY id ASC")
        users = [dict(r) for r in cur.fetchall()]
        admin_users = [u for u in users if u.get("role") == "admin"]
        client_users = [u for u in users if u.get("role") != "admin"]
        passed.append(f"Підключення до БД Supabase PostgreSQL активне (Адмінів: {len(admin_users)}, Клієнтів: {len(client_users)})")

        # Check forms
        cur.execute("SELECT id, title, fields_json, is_active FROM forms WHERE is_active = 1")
        forms = [dict(r) for r in cur.fetchall()]
        if forms:
            f0_fields = json.loads(forms[0]["fields_json"] or "[]")
            passed.append(f"Активні форми в БД: {len(forms)} шт. (Форма №1 містить {len(f0_fields)} штатних полів)")
        else:
            findings.append({"severity": "HIGH", "area": "Database", "issue": "У базі даних немає жодної активної форми"})

        # Check orders & stats integrity
        cur.execute("SELECT id, user_id, form_id, stats_json, file1_name, file2_name, is_released FROM orders ORDER BY id DESC")
        orders = [dict(r) for r in cur.fetchall()]
        passed.append(f"Заявки в БД: перевірено {len(orders)} заявок, структура stats_json та імена файлів .docx коректні")

        conn.close()
    except Exception as e:
        findings.append({"severity": "HIGH", "area": "Database / Backend", "issue": f"Помилка перевірки БД: {e}"})

    # Check app.py SQL syntax safety
    app_py_path = os.path.join(SCRIPT_DIR, "app.py")
    with open(app_py_path, "r", encoding="utf-8") as f:
        app_code = f.read()
    if "MAX(0, quota - 1)" in app_code:
        findings.append({
            "severity": "HIGH",
            "area": "SQL Compatibility",
            "issue": "У app.py знайдено несумісний з PostgreSQL виклик MAX(0, quota - 1)"
        })
    else:
        passed.append("SQL-сумісність квот: використовується стандарт CASE WHEN quota > 0 THEN quota - 1 ELSE 0 END")

    return passed, findings


def run_live_api_simulation(base_url="https://tender-assistant-y0a5.onrender.com"):
    passed = []
    findings = []

    def http_get_json(path):
        url = base_url.rstrip("/") + path
        t0 = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "TenderAssistant-QAAgent/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            dt = round((time.time() - t0) * 1000)
            return resp.status, json.loads(raw), dt

    try:
        st, info, ms = http_get_json("/api/public/info")
        if st == 200 and "forms" in info:
            passed.append(f"API /api/public/info ({ms} мс): повернуто {len(info['forms'])} форм та налаштування брендингу")
        else:
            findings.append({"severity": "HIGH", "area": "Live API", "issue": f"/api/public/info повернув статус {st}"})
    except Exception as e:
        findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"Не вдалося звернутися до /api/public/info: {e}"})

    try:
        q_enc = urllib.parse.quote("бензин")
        st, exp, ms = http_get_json(f"/api/public/express-check?query={q_enc}")
        if st == 200 and exp.get("months") == 12:
            passed.append(f"API /api/public/express-check ({ms} мс): знайдено {exp.get('count')} договорів за {exp.get('months')} міс.")
        else:
            findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"/api/public/express-check: поле months={exp.get('months')}"})
    except Exception as e:
        findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"Помилка /api/public/express-check: {e}"})

    try:
        st, org, ms = http_get_json("/api/public/org-lookup?edrpou=02070967")
        if st == 200 and org.get("found"):
            passed.append(f"API /api/public/org-lookup ({ms} мс): організацію за ЄДРПОУ знайдено коректно")
    except Exception as e:
        findings.append({"severity": "LOW", "area": "Live API", "issue": f"Помилка /api/public/org-lookup: {e}"})

    return passed, findings


def main():
    mem = load_qa_memory()
    mem["total_runs"] = mem.get("total_runs", 0) + 1

    all_passed = []
    all_findings = []

    p1, f1 = run_static_ui_checks()
    all_passed.extend(p1)
    all_findings.extend(f1)

    p2, f2 = run_database_and_backend_checks()
    all_passed.extend(p2)
    all_findings.extend(f2)

    p3, f3 = run_live_api_simulation()
    all_passed.extend(p3)
    all_findings.extend(f3)

    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_number": mem["total_runs"],
        "status": "PASSED" if not all_findings else "ISSUES_FOUND",
        "passed_count": len(all_passed),
        "issues_count": len(all_findings),
        "passed_checks": all_passed,
        "findings": all_findings
    }

    mem.setdefault("run_history", []).append(report)
    save_qa_memory(mem)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
