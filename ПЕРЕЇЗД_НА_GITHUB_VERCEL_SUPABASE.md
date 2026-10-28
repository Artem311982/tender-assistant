# Покроковий план переїзду веб-платформи «Тендерний помічник» у хмару: GitHub + Vercel + Supabase (PostgreSQL)

Цей документ містить вичерпну покрокову інструкцію з міграції проекту з локального комп'ютера на сучасний хмарний стек:
* **GitHub** — версійний контроль та автоматичний деплой (CI/CD).
* **Vercel** — швидкісний хостинг фронтенду та Serverless API на глобальній CDN.
* **Supabase** — надійна хмарна реляційна база даних PostgreSQL та сховище для згенерованих файлів Word (`.docx`).

---

## ⚖️ Чому Supabase (PostgreSQL) доцільніший за Firebase?

| Критерій | Supabase (PostgreSQL) | Google Firebase (Firestore) |
| :--- | :--- | :--- |
| **Тип бази даних** | **Реляційна SQL (Ідеально підходить)** | NoSQL (Документо-орієнтована) |
| **Сумісність з проектом** | **99% збіг** із поточною SQLite (таблиці, зв'язки, типи даних) | Потребує повного переписування логіки вибірок та зв'язків |
| **Сховище файлів (.docx)** | **Вбудоване Supabase Storage** (S3-сумісне) | Firebase Cloud Storage |
| **Швидкість міграції** | **15–20 хвилин** (простий експорт SQL-схеми) | Кілька днів на рефакторинг |
| **Безкоштовний тариф** | 500 МБ БД, 1 ГБ сховища, 50 000 користувачів щомісяця | Обмеження на операції читання/запису |

> [!TIP]
> **Висновок:** **Supabase** — ідеальний вибір для аналітичних та тендерних систем з реляційними зв'язками між користувачами, квотами, заявками та тарифами.

---

## 🏛 Архітектура після міграції

```mermaid
flowchart TD
    User["Клієнти / Користувачі<br/>(Смартфони / Ноутбуки)"] -->|"HTTPS (Глобальний CDN)"| Vercel["Vercel Cloud Platform<br/>• Фронтенд (HTML, CSS, JS)<br/>• Serverless Python API (/api)"]
    GitHub["GitHub Репозиторій<br/>(github.com/ваше-ім'я/tender-pomichnyk)"] -->|"Автодеплой при push (CI/CD)"| Vercel
    Vercel <-->|"PostgreSQL Connection (SSL)"| SupabaseDB[("Supabase PostgreSQL<br/>(Користувачі, заявки, форми)")]
    Vercel <-->|"S3 API"| SupabaseStorage["Supabase Storage<br/>(Збережені .docx звіти)"]
    Vercel <-->|"HTTPS API"| Prozorro["Prozorro API<br/>(ЦБД та пошуковий рушій)"]
```

---

## 📋 Покроковий план виконання робіт

### КРОК 1. Підготовка структури файлів проекту до хмари

1. **Створення файлу `.gitignore`:**
   Виключаємо локальні файли, конфіденційні паролі та бінарні файли, які не мають потрапляти на GitHub:
   ```gitignore
   # Локальні бази та логи
   Пам'ять/
   *.log
   *.db
   *.sqlite3

   # Бінарні файли та системні скрипти Windows
   cloudflared.exe
   *.exe
   *.zip
   *.bat
   *.vbs
   *.url

   # Python кеш
   __pycache__/
   *.pyc
   .venv/
   env/
   ```

2. **Створення файлу залежностей `requirements.txt`:**
   ```text
   python-docx>=1.1.0
   openpyxl>=3.1.2
   pypdf>=5.0.0
   psycopg2-binary>=2.9.9
   supabase>=2.3.0
   requests>=2.31.0
   ```

3. **Створення конфігурації для Vercel (`vercel.json`):**
   ```json
   {
     "rewrites": [
       { "source": "/api/(.*)", "destination": "/api/index.py" },
       { "source": "/(.*)", "destination": "/static/$1" }
     ]
   }
   ```

---

### КРОК 2. Налаштування бази даних у Supabase (5 хвилин)

1. Перейдіть на сайт **[supabase.com](https://supabase.com)** та увійдіть через кнопку **«Continue with GitHub»** або Google.
2. Натисніть **«New Project»** (Створити новий проект):
   * **Name:** `tender-assistant`
   * **Database Password:** вкажіть надійний пароль (обов'язково збережіть його).
   * **Region:** виберіть найближчий європейський датацентр (наприклад, `Central EU (Frankfurt)`).
3. Після створення проекту відкрийте розділ **SQL Editor** та виконайте скрипт створення таблиць (нижче у додатку).
4. У розділі **Project Settings → Database** скопіюйте рядок підключення:
   `postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

---

### КРОК 3. Створення репозиторію на GitHub та вивантаження коду

1. Перейдіть на **[github.com](https://github.com)** та створіть новий репозиторій:
   * **Repository name:** `tender-assistant-platform`
   * **Visibility:** `Private` (рекомендовано для захисту вашого авторського коду) або `Public`.
2. У терміналі на вашому комп'ютері виконайте команди прив'язки:
   ```bash
   cd "C:\Projects\Тендерний помічник"
   git init
   git add .
   git commit -m "Initial commit for Vercel & Supabase deployment"
   git branch -M main
   git remote add origin https://github.com/ВАШ_ЛОГІН_GITHUB/tender-assistant-platform.git
   git push -u origin main
   ```

---

### КРОК 4. Деплой на Vercel (2 хвилини)

1. Перейдіть на **[vercel.com](https://vercel.com)** та увійдіть за допомогою вашого GitHub-акаунта.
2. Натисніть кнопку **«Add New...» → «Project»**.
3. Виберіть ваш репозиторій `tender-assistant-platform` та натисніть **«Import»**.
4. У блоці **«Environment Variables»** (Змінні середовища) додайте:
   * `DATABASE_URL` = ваш рядок підключення до Supabase PostgreSQL.
   * `SUPABASE_URL` = URL вашого проекту в Supabase.
   * `SUPABASE_KEY` = публічний anon-ключ із налаштувань Supabase.
5. Натисніть **«Deploy»**. 
6. Через 45–60 секунд Vercel видасть готову безкоштовну світову адресу:
   👉 **`https://tender-assistant-platform.vercel.app`**

---

### КРОК 5. Підключення власного домену (за бажанням)

* У панелі Vercel перейдіть у **Settings → Domains**.
* Введіть свій домен (наприклад, `tender-pomichnyk.com.ua` чи безкоштовний `.pp.ua`).
* Vercel автоматично безкоштовно згенерує офіційний SSL-сертифікат HTTPS (Let's Encrypt).

---

## 🗄 Додаток: SQL-схема для створення таблиць у Supabase

```sql
-- Користувачі та клієнти
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
    account_type VARCHAR(50) DEFAULT 'buyer',
    delivery_override VARCHAR(50) DEFAULT 'manual',
    quota INT DEFAULT 5,
    is_active INT DEFAULT 1,
    permissions_json TEXT DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Сесії
CREATE TABLE IF NOT EXISTS sessions (
    token VARCHAR(255) PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Скидання паролів
CREATE TABLE IF NOT EXISTS password_resets (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_used INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Заявки та розрахунки
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    form_id INT NOT NULL,
    input_data_json TEXT NOT NULL,
    benchmarks_json TEXT DEFAULT '[]',
    stats_json TEXT DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    result_docx_name VARCHAR(255) DEFAULT '',
    result_annex_docx_name VARCHAR(255) DEFAULT '',
    uploaded_docx_name VARCHAR(255) DEFAULT '',
    is_released INT DEFAULT 1
);

-- Налаштування сайту
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL
);
```
