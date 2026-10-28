import os
import sys

# Ensure project root and scripts directory are in Python module search path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "Скрипти")

for d in [PROJECT_ROOT, SCRIPTS_DIR]:
    if d not in sys.path:
        sys.path.insert(0, d)

from app import TenderAppHandler

# Export handler class for Vercel Serverless Function runtime
class handler(TenderAppHandler):
    pass
