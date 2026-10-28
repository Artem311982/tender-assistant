-- ==============================================================
-- БАЗА ДАНИХ АНАЛІТИЧНОГО ЦЕНТРУ «ТЕНДЕРНИЙ ПОМІЧНИК» (SUPABASE POSTGRESQL)
-- ПРОЄКТ: ixrbpktmwyuvaseetbyb
-- ==============================================================

-- 1. СТВОРЕННЯ ТАБЛИЦЬ

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    org_name VARCHAR(255) DEFAULT '',
    edrpou VARCHAR(50) DEFAULT '',
    phone VARCHAR(50) DEFAULT '',
    address TEXT DEFAULT '',
    director_name VARCHAR(255) DEFAULT '',
    director_title VARCHAR(255) DEFAULT '',
    website VARCHAR(255) DEFAULT '',
    role VARCHAR(50) DEFAULT 'user',
    account_type VARCHAR(50) DEFAULT 'user',
    delivery_override VARCHAR(50) DEFAULT 'default',
    quota INT DEFAULT 10,
    is_active INT DEFAULT 1,
    permissions_json TEXT DEFAULT '{}',
    authorized_persons_json TEXT DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    token VARCHAR(255) PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS password_resets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_used INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS forms (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    fields_json TEXT NOT NULL,
    docx_template_path TEXT DEFAULT '',
    is_active INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    form_id INT NOT NULL,
    form_title TEXT DEFAULT '',
    is_released INT DEFAULT 0,
    payment_status VARCHAR(50) DEFAULT 'unpaid',
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback_messages (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT DEFAULT 0,
    sender_name VARCHAR(255) DEFAULT '',
    sender_email VARCHAR(255) DEFAULT '',
    sender_org VARCHAR(255) DEFAULT '',
    sender_edrpou VARCHAR(50) DEFAULT '',
    subject VARCHAR(255) DEFAULT '',
    message TEXT NOT NULL,
    admin_reply TEXT DEFAULT '',
    status VARCHAR(50) DEFAULT 'new',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    replied_at TIMESTAMP WITH TIME ZONE
);

-- 2. ПОЧАТКОВІ ДАНІ (НАЛАШТУВАННЯ, АДМІНІСТРАТОР, КЛІЄНТ, ФОРМИ)

-- Налаштування
INSERT INTO settings (key, value) VALUES ('delivery_mode', 'manual') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('service_title', 'Створення порівняння цін у системі Prozorro та обґрунтувань за Постановою КМУ № 710 і № 1178') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('platform_name', 'Аналітичний центр «Тендерний помічник»') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('platform_subtitle', '') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('logo_data_url', '') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('contact_email', '') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO settings (key, value) VALUES ('contact_phone', '') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Адміністратор (Артем Володимирович)
INSERT INTO users (id, email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, authorized_persons_json)
VALUES (1, 'artemvolodymyrovych@gmail.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'Артем Володимирович (Адміністратор)', 'Аналітичний центр «Тендерний помічник»', '00000000', '+380960000000', 'м. Миколаїв', 'Артем Володимирович', 'Керівник проєкту', 'https://prozorro.gov.ua', 'admin', 'admin', 'auto', 999, 1, '{"access_level": "full", "can_create_orders": true, "can_prozorro_autofill": true, "can_docx_upload": true, "can_view_price_table": true, "can_download_main_doc": true, "can_download_annex_doc": true, "can_view_legal_variants": true}', '[]')
ON CONFLICT (email) DO UPDATE SET 
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    quota = EXCLUDED.quota;

-- Перший клієнт (Людмила ШУМОВА / НУК ім. адм. Макарова)
INSERT INTO users (id, email, password_hash, full_name, org_name, edrpou, phone, address, director_name, director_title, website, role, account_type, delivery_override, quota, is_active, permissions_json, authorized_persons_json)
VALUES (2, 'lyudmyla.shumova@nuos.edu.ua', 'e606e38b0d8c19b24cf0ee3808183162ea7cd63ff7912dbb22b5e803286b4446', 'Людмила ШУМОВА', 'НАЦІОНАЛЬНИЙ УНІВЕРСИТЕТ КОРАБЛЕБУДУВАННЯ ІМЕНІ АДМІРАЛА МАКАРОВА', '02066753', '+380964141094', '54007, Україна, Миколаївська область, м. Миколаїв, просп. Героїв України, буд. 9', 'Євген ТРУШЛЯКОВ', 'Ректор Національного університету кораблебудування імені адмірала Макарова', 'https://nuos.edu.ua', 'user', 'client', 'auto', 19, 1, '{"access_level": "full", "can_create_orders": true, "can_prozorro_autofill": true, "can_docx_upload": true, "can_view_price_table": true, "can_download_main_doc": true, "can_download_annex_doc": true, "can_view_legal_variants": false, "can_edit_org_details": false}', '[]')
ON CONFLICT (email) DO UPDATE SET 
    org_name = EXCLUDED.org_name,
    edrpou = EXCLUDED.edrpou;

-- Форми закупівлі (Форма 1 та Форма 2)
INSERT INTO forms (id, title, description, fields_json, is_active)
VALUES (
    1,
    'Форма № 1: Інформація для проведення аналізу цін (базова)',
    'Сформована на основі документа «Інформація для проведення аналізу цін.docx» з додатковими полями очікуваної вартості та обсягу закупівлі.',
    '[{"key": "buyer_name", "label": "Найменування замовника", "type": "text", "required": true}, {"key": "edrpou", "label": "Код ЄДРПОУ", "type": "text", "required": true}, {"key": "subject_name", "label": "Конкретна назва предмета закупівлі", "type": "text", "required": true}, {"key": "cpv_code", "label": "Код ДК 021:2015 (CPV 2008, IDT)", "type": "text", "required": true}, {"key": "expected_value", "label": "Очікувана вартість предмета закупівлі (без ПДВ, грн)", "type": "number", "required": true}, {"key": "quantity", "label": "Кількість (обсяг закупівлі)", "type": "number", "required": true}, {"key": "unit_name", "label": "Одиниця виміру (Гкал, шт, послуга тощо)", "type": "text", "required": true}, {"key": "tender_id", "label": "Ідентифікатор закупівлі в Prozorro (UA-... за наявності)", "type": "text", "required": false}]',
    1
) ON CONFLICT (id) DO NOTHING;

INSERT INTO forms (id, title, description, fields_json, is_active)
VALUES (
    2,
    'Форма № 2: Повна форма Обґрунтування (Постанова № 710 + Аналіз цін Prozorro)',
    'Розширена форма з усіма реквізитами замовника, місцями поставки та технічними характеристиками за зразком НУК ім. адм. Макарова.',
    '[{"key": "tender_id", "label": "Ідентифікатор закупівлі в Prozorro (UA-...)", "type": "text", "required": true}, {"key": "plan_id", "label": "Ідентифікатор плану закупівлі в Prozorro", "type": "text", "required": false}, {"key": "buyer_name", "label": "Найменування замовника", "type": "text", "required": true}, {"key": "edrpou", "label": "Код ЄДРПОУ замовника", "type": "text", "required": true}, {"key": "buyer_address", "label": "Місцезнаходження (юридична адреса) замовника", "type": "text", "required": true}, {"key": "director_title", "label": "Посада керівника (для грифу ЗАТВЕРДЖУЮ)", "type": "text", "required": true}, {"key": "director_name", "label": "Власне ім''я ПРІЗВИЩЕ керівника", "type": "text", "required": true}, {"key": "authorized_person", "label": "Власне ім''я ПРІЗВИЩЕ уповноваженої особи", "type": "text", "required": true}, {"key": "phone", "label": "Телефон уповноваженої особи", "type": "text", "required": false}, {"key": "website", "label": "Офіційний веб-сайт замовника (для оприлюднення за Постановою № 710)", "type": "text", "required": false}, {"key": "subject_name", "label": "Конкретна назва предмета закупівлі", "type": "text", "required": true}, {"key": "cpv_code", "label": "Код ДК 021:2015 (CPV)", "type": "text", "required": true}, {"key": "quantity", "label": "Кількість (плановий обсяг закупівлі)", "type": "number", "required": true}, {"key": "unit_name", "label": "Одиниця виміру", "type": "text", "required": true}, {"key": "expected_value", "label": "Очікувана вартість предмета закупівлі (без ПДВ, грн)", "type": "number", "required": true}, {"key": "kekv", "label": "Код економічної класифікації видатків (КЕКВ)", "type": "text", "required": false}, {"key": "delivery_term", "label": "Строк поставки товарів / надання послуг", "type": "text", "required": false}, {"key": "delivery_address", "label": "Місця поставки (кожна адреса з нового рядка)", "type": "textarea", "required": false}, {"key": "tech_specs", "label": "Технічні та якісні характеристики предмета закупівлі", "type": "textarea", "required": false}]',
    1
) ON CONFLICT (id) DO NOTHING;

-- Оновлюємо послідовності ідентифікаторів
SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
SELECT setval('forms_id_seq', (SELECT MAX(id) FROM forms));
