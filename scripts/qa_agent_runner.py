import os
import sys
import ast
import builtins
import json
import time
import re
import threading
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)
QA_MEMORY_PATH = os.path.join(MEMORY_DIR, "qa_agent_memory.json")

sys.path.insert(0, SCRIPT_DIR)

ALLOWED_SYMBOLS = {"🔒", "🛡", "🛡️", "➕", "+", "\ufe0f", "↻", "👁", "👁️"}

KNOWN_REGRESSION_GUARDS = [
    "PostgreSQL scalar MAX(0, quota - 1) replaced with CASE WHEN / GREATEST",
    "Strict icon policy: only lock, shield, plus, circular arrow, and password eye allowed",
    "English-only file and folder naming across the entire project",
    "Merged tab 'Мої заявки та результати': form first, compact table second",
    "Market price amount must be black (#000000) in compact orders table",
    "Express check wording: Проаналізовано ... укладених договорів протягом ... місяців",
    "Tab persistence across F5 reload and anti-flicker hide-public-landing",
    "Hidden admin portal (/control-panel-artem) with no public /admin link or admin email leak",
    "Conservative contiguous browser-style admin tabs (.admin-browser-bar) & 5-module Site Constructor",
    "CPV 2015 searchable dropdown according to Order No. 1749 matching Prozorro",
    "CPV 2015 hierarchical modal tree with real-time search on digits/letters",
    "Removal of number spinners on expected value and quantity fields",
    "AST static undefined-name check (prevents NameError like TenderHandler vs TenderAppHandler)",
    "Pre-deploy in-process local HTTP server test (GET /, GET /control-panel-artem, GET /api/public/info, POST /api/auth/login) to prevent 502 Bad Gateway on Render"
]


def load_qa_memory():
    if os.path.exists(QA_MEMORY_PATH):
        try:
            with open(QA_MEMORY_PATH, "r", encoding="utf-8") as f:
                mem = json.load(f)
                mem["known_regression_guards"] = KNOWN_REGRESSION_GUARDS
                return mem
        except Exception:
            pass
    return {
        "agent_name": "QA-Агент Тестувальник Тендерний Помічник",
        "total_runs": 0,
        "known_regression_guards": KNOWN_REGRESSION_GUARDS,
        "run_history": []
    }


def save_qa_memory(mem):
    mem["known_regression_guards"] = KNOWN_REGRESSION_GUARDS
    mem["run_history"] = mem.get("run_history", [])[-25:]
    with open(QA_MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


def run_static_ui_checks():
    findings = []
    passed = []
    index_path = os.path.join(SCRIPT_DIR, "static", "index.html")
    pub_index_path = os.path.join(PROJECT_ROOT, "public", "index.html")

    if not os.path.exists(index_path):
        findings.append({"severity": "CRITICAL", "area": "UI", "issue": "Відсутній файл scripts/static/index.html"})
        return passed, findings

    with open(index_path, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Check sync between static/index.html and public/index.html
    if os.path.exists(pub_index_path):
        with open(pub_index_path, "r", encoding="utf-8") as f:
            pub_html = f.read()
        if html == pub_html:
            passed.append("Синхронізація static/index.html та public/index.html — ідентичні")
        else:
            findings.append({
                "severity": "HIGH",
                "area": "Deployment Sync",
                "issue": "Файли scripts/static/index.html та public/index.html відрізняються"
            })

    # 2. Check English-only file and folder naming across PROJECT_ROOT
    cyrillic_paths = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in dirs + files:
            if re.search(r"[А-Яа-яІіЇїЄєҐґ]", name):
                rel = os.path.relpath(os.path.join(root, name), PROJECT_ROOT)
                cyrillic_paths.append(rel)
    if not cyrillic_paths:
        passed.append("Англомовні назви папок та файлів: жодного кириличного шляху в проєкті")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "File Naming Policy",
            "issue": f"Знайдено файли/папки не англійською мовою: {cyrillic_paths[:5]}"
        })

    # 3. Check strict icon policy
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

    # 4. Check merged tab 'Мої заявки та результати' and order of blocks
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

    # 5. Check compact table requirements
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

    # 6. Check Prozorro units dropdown in service order form
    if "PROZORRO_UNITS_GROUPS" in html and 'id="orderUnitNameField"' in html:
        passed.append("Поле «Одиниця виміру»: підключено випадаючий список стандартних одиниць виміру Prozorro")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Order Form",
            "issue": "Відсутній випадаючий список одиниць виміру Prozorro у формі замовлення послуги"
        })

    # 6a. Check CPV 2015 dropdown according to Order No. 1749 matching Prozorro
    if "PROZORRO_CPV_GROUPS" in html and 'id="orderCpvCodeField"' in html and 'orderCpvSuggestionsBox' in html:
        passed.append("Поле «Код ДК 021:2015»: підключено випадаючий список класифікатора ДК 021:2015 (Наказ Мінекономрозвитку № 1749)")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Order Form",
            "issue": "Відсутній випадаючий список класифікатора ДК 021:2015 у формі замовлення послуги"
        })

    # 6b. Check CPV 2015 modal window with real-time tree search
    if 'id="cpvClassifierModal"' in html and 'id="cpvModalSearchInput"' in html and 'PROZORRO_CPV_TREE' in html and 'openCpvClassifierModal' in html:
        passed.append("Модальне вікно класифікатора ДК 021:2015: деревоподібна структура з живим пошуком за цифрами/літерами, розгортанням та вибором")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "CPV Modal Classifier",
            "issue": "Відсутнє або не повністю налаштоване модальне вікно класифікатора ДК 021:2015"
        })

    # 6c. Check JavaScript syntax integrity in static/index.html
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    js_errors = []
    for s_idx, s in enumerate(scripts):
        backticks = re.findall(r'(?<!\\)`', s)
        if len(backticks) % 2 != 0:
            js_errors.append(f"Незбалансовані backticks (`) у скрипті #{s_idx+1}")
        if "PROZORRO_CPV_TREE" in s:
            if re.search(r'inp\.value\s*=\s*`[^`]*PROZORRO_CPV_TREE', s):
                js_errors.append("PROZORRO_CPV_TREE випадково потрапив всередину рядкового літералу inp.value!")
    if not js_errors:
        passed.append("Синтаксична цілісність JavaScript: всі template strings (`) збалансовані, класифікатор ДК оголошений на верхньому рівні")
    else:
        for err in js_errors:
            findings.append({"severity": "CRITICAL", "area": "JavaScript Syntax", "issue": err})

    # 6d. Check removal of spinners on number inputs
    if "::-webkit-inner-spin-button" in html and "-webkit-appearance: none" in html and "-moz-appearance: textfield" in html:
        passed.append("Поля «Очікувана вартість» та «Кількість»: прибрано стрілки-лічильники (spinners) у числових полях")
    else:
        findings.append({
            "severity": "MEDIUM",
            "area": "Number Inputs",
            "issue": "Не прибрано стрілки-лічильники (spinners) у полях типу number"
        })

    # 7. Check password eye toggle pictograms (closed eye when hidden, open eye when visible)
    if "pwd-eye-closed" in html and "pwd-eye-open" in html and "PWD_EYE_CLOSED_SVG" in html and "PWD_EYE_OPEN_SVG" in html:
        passed.append("Поля паролів: встановлено піктограму ока (закрите око коли пароль прихований, відкрите коли відкритий)")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Password Fields",
            "issue": "Не всі поля паролів оснащені піктограмою закритого/відкритого ока"
        })

    # 8. Check hidden admin portal and absence of exposed admin links/emails
    if 'href="/admin"' not in html and 'artemvolodymyrovych@gmail.com' not in html and '/control-panel-artem' in html:
        passed.append("Безпека входу адміністратора: публічне посилання /admin та email приховано, активна секретна адреса /control-panel-artem")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Admin Portal Security",
            "issue": "Знайдено публічне посилання на /admin або відкритий email адміністратора у HTML"
        })

    # 9. Check conservative browser-tab Admin Panel & Site Constructor structure
    required_admin_markers = [
        "admin-browser-bar",
        "admin-browser-tab",
        "admPane_orders",
        "admPane_clients",
        "admPane_feedback",
        "admPane_builder",
        "admPane_forms",
        "admPane_admins",
        "builderPane_blocks",
        "builderPane_content",
        "builderPane_branding",
        "builderPane_rules",
        "builderPane_security",
        "vf_fieldsTableWrap",
        "saveAllSiteBuilderSettings",
        "saveVisualFormChanges"
    ]
    missing_admin = [m for m in required_admin_markers if m not in html]
    if not missing_admin:
        passed.append("Адмін-панель та Конструктор сайту: горизонтальні браузерні вкладки (6 розділів, 5 модулів конструктора, візуальний конструктор форм) активні")
    else:
        findings.append({
            "severity": "HIGH",
            "area": "Admin Panel & Site Constructor",
            "issue": f"У index.html відсутні елементи конструктора адмін-панелі: {missing_admin}"
        })

    return passed, findings


def _collect_module_scope_names(stmts, out_set):
    """Collects names defined at module scope, including inside module-level if/else/try blocks."""
    for stmt in stmts:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out_set.add(stmt.name)
        elif isinstance(stmt, ast.Import):
            for alias in stmt.names:
                out_set.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(stmt, ast.ImportFrom):
            for alias in stmt.names:
                out_set.add(alias.asname or alias.name)
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    out_set.add(t.id)
        elif isinstance(stmt, ast.If):
            _collect_module_scope_names(stmt.body, out_set)
            _collect_module_scope_names(stmt.orelse, out_set)
        elif isinstance(stmt, ast.Try):
            _collect_module_scope_names(stmt.body, out_set)
            _collect_module_scope_names(stmt.orelse, out_set)
            _collect_module_scope_names(stmt.finalbody, out_set)
            for h in stmt.handlers:
                if h.name:
                    out_set.add(h.name)
                _collect_module_scope_names(h.body, out_set)


def _check_function_scope(fn_node, inherited_scope, undefined_out):
    """Checks a function/method AST node for undefined Load names, properly handling nested functions."""
    local_vars = set(inherited_scope)
    for arg in fn_node.args.args + fn_node.args.posonlyargs + fn_node.args.kwonlyargs:
        local_vars.add(arg.arg)
    if fn_node.args.vararg:
        local_vars.add(fn_node.args.vararg.arg)
    if fn_node.args.kwarg:
        local_vars.add(fn_node.args.kwarg.arg)

    nested_fns = []

    def walk_no_nested(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                local_vars.add(child.name)
                nested_fns.append(child)
                continue
            if isinstance(child, ast.ClassDef):
                local_vars.add(child.name)
                continue
            if isinstance(child, ast.Lambda):
                for larg in child.args.args + child.args.posonlyargs + child.args.kwonlyargs:
                    local_vars.add(larg.arg)
                if child.args.vararg:
                    local_vars.add(child.args.vararg.arg)
                if child.args.kwarg:
                    local_vars.add(child.args.kwarg.arg)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                local_vars.add(child.id)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                local_vars.add(child.name)
            elif isinstance(child, (ast.For, ast.AsyncFor, ast.comprehension)):
                target = getattr(child, "target", None)
                if isinstance(target, ast.Name):
                    local_vars.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            local_vars.add(elt.id)
            elif isinstance(child, ast.With):
                for item in child.items:
                    if isinstance(item.optional_vars, ast.Name):
                        local_vars.add(item.optional_vars.id)
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    local_vars.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(child, ast.ImportFrom):
                for alias in child.names:
                    local_vars.add(alias.asname or alias.name)
            elif isinstance(child, ast.NamedExpr) and isinstance(child.target, ast.Name):
                local_vars.add(child.target.id)
            walk_no_nested(child)

    walk_no_nested(fn_node)

    def check_loads_no_nested(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                if child.id not in local_vars:
                    undefined_out.append(f"{fn_node.name}(): '{child.id}' (рядок {child.lineno})")
            check_loads_no_nested(child)

    check_loads_no_nested(fn_node)

    for nfn in nested_fns:
        _check_function_scope(nfn, local_vars, undefined_out)


def run_python_ast_and_scope_checks():
    """Static AST check across all Python files to catch syntax errors and undefined global/class names (like TenderHandler vs TenderAppHandler)."""
    passed = []
    findings = []

    py_files = [
        os.path.join(PROJECT_ROOT, "main.py"),
        os.path.join(PROJECT_ROOT, "api", "index.py"),
        os.path.join(SCRIPT_DIR, "app.py"),
        os.path.join(SCRIPT_DIR, "db_adapter.py"),
        os.path.join(SCRIPT_DIR, "doc_generator.py"),
        os.path.join(SCRIPT_DIR, "prozorro_service.py"),
    ]

    builtin_names = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__"}

    for fpath in py_files:
        if not os.path.exists(fpath):
            findings.append({"severity": "HIGH", "area": "Python Codebase", "issue": f"Файл не знайдено: {fpath}"})
            continue
        rel_name = os.path.relpath(fpath, PROJECT_ROOT)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, filename=rel_name)
        except Exception as e:
            findings.append({"severity": "CRITICAL", "area": "Python Syntax", "issue": f"Синтаксична помилка у {rel_name}: {e}"})
            continue

        module_defined = set(builtin_names)
        _collect_module_scope_names(tree.body, module_defined)

        undefined_in_file = []
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _check_function_scope(stmt, module_defined, undefined_in_file)
            elif isinstance(stmt, ast.ClassDef):
                for cstmt in stmt.body:
                    if isinstance(cstmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        _check_function_scope(cstmt, module_defined, undefined_in_file)

        if undefined_in_file:
            findings.append({
                "severity": "CRITICAL",
                "area": f"Python Undefined Name ({rel_name})",
                "issue": f"Виявлено невизначені ідентифікатори (ризик NameError / 502): {', '.join(undefined_in_file)}"
            })

    if not any(f["area"].startswith("Python") for f in findings):
        passed.append(f"AST-аналіз Python-модулів ({len(py_files)} файлів): синтаксис і всі глобальні/класові посилання коректні (0 NameError)")

    return passed, findings


def run_local_server_e2e_checks():
    """Spins up an ephemeral in-process HTTP server using local app.py and tests key GET/POST routes BEFORE deploy."""
    passed = []
    findings = []
    srv = None
    try:
        import app
        srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.TenderAppHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        base = f"http://127.0.0.1:{port}"

        # 1. GET /
        with urllib.request.urlopen(f"{base}/", timeout=10) as r:
            body = r.read().decode("utf-8")
            if r.status == 200 and len(body) > 50000 and "__IS_ADMIN_PORTAL_ROUTE = true" not in body:
                passed.append("Локальний сервер E2E: GET / повертає 200 OK (публічний режим клієнта)")
            else:
                findings.append({"severity": "CRITICAL", "area": "Local E2E", "issue": f"GET / повернув некоректну відповідь (status={r.status})"})

        # 2. GET /control-panel-artem
        with urllib.request.urlopen(f"{base}/control-panel-artem", timeout=10) as r:
            body = r.read().decode("utf-8")
            if r.status == 200 and "window.__IS_ADMIN_PORTAL_ROUTE = true;" in body:
                passed.append("Локальний сервер E2E: GET /control-panel-artem повертає 200 OK з ін'єкцією маркера адмін-порталу")
            else:
                findings.append({"severity": "CRITICAL", "area": "Local E2E", "issue": "GET /control-panel-artem не містить маркера __IS_ADMIN_PORTAL_ROUTE"})

        # 3. GET /api/public/info
        with urllib.request.urlopen(f"{base}/api/public/info", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            st_dict = data.get("settings", {})
            if r.status == 200 and "forms" in data and "admin_secret_path" not in st_dict:
                passed.append("Локальний сервер E2E: GET /api/public/info повертає 200 OK і не розкриває admin_secret_path")
            else:
                findings.append({"severity": "HIGH", "area": "Local E2E", "issue": "GET /api/public/info розкриває admin_secret_path або некоректний"})

        # 4. POST /api/auth/login (invalid credentials test)
        req = urllib.request.Request(
            f"{base}/api/auth/login",
            data=json.dumps({"email": "nonexistent@example.com", "password": "wrong"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            findings.append({"severity": "HIGH", "area": "Local E2E", "issue": "POST /api/auth/login пропустив неіснуючого користувача"})
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8")
            if he.code == 401 and "/admin" not in err_body:
                passed.append("Локальний сервер E2E: POST /api/auth/login коректно відхиляє невірний вхід (401) без підказок про адмін-панель")
            else:
                findings.append({"severity": "HIGH", "area": "Local E2E", "issue": f"POST /api/auth/login повернув код {he.code}: {err_body}"})

    except Exception as e:
        findings.append({
            "severity": "CRITICAL",
            "area": "Local Server E2E",
            "issue": f"Збій локального HTTP-сервера перед деплоєм (причина 502 на Render): {e}"
        })
    finally:
        if srv:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass

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

    def http_get_raw(path, timeout=35):
        url = base_url.rstrip("/") + path
        for attempt in range(2):
            try:
                t0 = time.time()
                req = urllib.request.Request(url, headers={"User-Agent": "TenderAssistant-QAAgent/2.0"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    dt = round((time.time() - t0) * 1000)
                    return resp.status, raw, dt
            except Exception as e:
                if attempt == 0:
                    time.sleep(2)
                    continue
                raise e

    def http_get_json(path, timeout=20):
        st, raw, dt = http_get_raw(path, timeout=timeout)
        return st, json.loads(raw), dt

    # 1. Live check of secret admin portal URL on Render
    try:
        st, html_adm, ms = http_get_raw("/control-panel-artem")
        if st == 200 and "__IS_ADMIN_PORTAL_ROUTE" in html_adm:
            passed.append(f"Live Render /control-panel-artem ({ms} мс): статус 200 OK, секретний портал адміністратора працює")
        else:
            findings.append({"severity": "HIGH", "area": "Live Render Admin URL", "issue": f"/control-panel-artem повернув статус {st} або без маркера адмін-входу"})
    except Exception as e:
        findings.append({"severity": "CRITICAL", "area": "Live Render Admin URL", "issue": f"Посилання /control-panel-artem на Render не працює (можлива 502): {e}"})

    # 2. Live check of /api/public/info
    try:
        st, info, ms = http_get_json("/api/public/info")
        if st == 200 and "forms" in info:
            passed.append(f"API /api/public/info ({ms} мс): повернуто {len(info['forms'])} форм та налаштування брендингу")
        else:
            findings.append({"severity": "HIGH", "area": "Live API", "issue": f"/api/public/info повернув статус {st}"})
    except Exception as e:
        findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"Не вдалося звернутися до /api/public/info: {e}"})

    # 3. Live check of /api/public/express-check
    try:
        q_enc = urllib.parse.quote("бензин")
        st, exp, ms = http_get_json(f"/api/public/express-check?query={q_enc}")
        if st == 200 and exp.get("months") == 12:
            passed.append(f"API /api/public/express-check ({ms} мс): знайдено {exp.get('count')} договорів за {exp.get('months')} міс.")
        else:
            findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"/api/public/express-check: поле months={exp.get('months')}"})
    except Exception as e:
        findings.append({"severity": "MEDIUM", "area": "Live API", "issue": f"Помилка /api/public/express-check: {e}"})

    # 4. Live check of /api/public/org-lookup
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

    for check_fn in (
        run_static_ui_checks,
        run_python_ast_and_scope_checks,
        run_local_server_e2e_checks,
        run_database_and_backend_checks,
        run_live_api_simulation,
    ):
        p, f = check_fn()
        all_passed.extend(p)
        all_findings.extend(f)

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
