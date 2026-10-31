import os
import sys

# Додаємо папку скриптів до шляху пошуку модулів
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from app import run_server

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    run_server(port)
