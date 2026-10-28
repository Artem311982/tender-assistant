import os
import sys
import time
import re
import subprocess
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
APP_PY = os.path.join(SCRIPT_DIR, "app.py")
CLOUDFLARED_EXE = os.path.join(SCRIPT_DIR, "cloudflared.exe")
MEMORY_DIR = os.path.join(PROJECT_ROOT, "Пам'ять")
os.makedirs(MEMORY_DIR, exist_ok=True)

LOG_FILE = os.path.join(MEMORY_DIR, "platform_host.log")
ADDRESS_TXT = os.path.join(PROJECT_ROOT, "ПУБЛІЧНА_АДРЕСА_САЙТУ.txt")
DESKTOP_DIR = os.path.expanduser("~/Desktop")
DESKTOP_SHORTCUT = os.path.join(DESKTOP_DIR, "Тендерний помічник ОНЛАЙН.url")

def log(msg):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def is_local_server_healthy(port=8080):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/public/info", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False

def update_public_address_files(url):
    content = f"""==============================================================
 АНАЛІТИЧНИЙ ЦЕНТР «ТЕНДЕРНИЙ ПОМІЧНИК» — ОНЛАЙН АДРЕСА
==============================================================

 Ваша публічна адреса в інтернеті (працює на будь-якому пристрої):
 {url}

 Локальна адреса на цьому комп'ютері:
 http://127.0.0.1:8080

 Логін адміністратора:
 artemvolodymyrovych@gmail.com

 Дата оновлення підключення: {time.strftime('%Y-%m-%d %H:%M:%S')}
==============================================================
"""
    try:
        with open(ADDRESS_TXT, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        log(f"Помилка запису {ADDRESS_TXT}: {e}")

    # Створюємо швидкий ярлик на Робочому столі
    try:
        shortcut_content = f"[InternetShortcut]\nURL={url}\nIconIndex=0\n"
        with open(DESKTOP_SHORTCUT, "w", encoding="utf-8") as f:
            f.write(shortcut_content)
        log(f"Ярлик оновлено на робочому столі: {DESKTOP_SHORTCUT}")
    except Exception as e:
        log(f"Помилка створення ярлика на робочому столі: {e}")

def main():
    log("Запуск єдиного сервісу хостингу платформи «Тендерний помічник»...")

    server_proc = None
    tunnel_proc = None

    try:
        # 1. Запуск бекенд-сервера, якщо він ще не запущений
        if not is_local_server_healthy(8080):
            log("Запуск сервера Python app.py на порту 8080...")
            server_proc = subprocess.Popen(
                [sys.executable, "-u", APP_PY, "8080"],
                cwd=SCRIPT_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2)
        else:
            log("Локальний сервер на порту 8080 вже працює.")

        # 2. Запуск тунелю Cloudflare
        if not os.path.exists(CLOUDFLARED_EXE):
            log(f"ПОМИЛКА: Не знайдено {CLOUDFLARED_EXE}")
            return

        tunnel_cmd = [CLOUDFLARED_EXE, "tunnel", "--url", "http://127.0.0.1:8080"]
        log(f"Запуск публічного захищеного тунелю Cloudflare...")
        tunnel_proc = subprocess.Popen(
            tunnel_cmd,
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="ignore"
        )

        public_url = None

        # 3. Читання виводу та виявлення URL
        for line in tunnel_proc.stdout:
            cleaned = line.strip()
            if cleaned:
                # Шукаємо посилання trycloudflare.com
                m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', cleaned)
                if m and not public_url:
                    public_url = m.group(0)
                    log("=" * 60)
                    log(f"УСПІХ! ПУБЛІЧНА АДРЕСА САЙТУ: {public_url}")
                    log("=" * 60)
                    update_public_address_files(public_url)

            # Моніторинг здоров'я кожні 30 секунд
            if tunnel_proc.poll() is not None:
                log("Тунель Cloudflare завершив роботу. Перезапуск...")
                break

    except KeyboardInterrupt:
        log("Отримано сигнал зупинки від користувача.")
    except Exception as e:
        log(f"Помилка в роботі хост-сервісу: {e}")
    finally:
        log("Завершення процесів...")
        if tunnel_proc and tunnel_proc.poll() is None:
            tunnel_proc.terminate()
        if server_proc and server_proc.poll() is None:
            server_proc.terminate()
        log("Сервіс зупинено.")

if __name__ == "__main__":
    main()
