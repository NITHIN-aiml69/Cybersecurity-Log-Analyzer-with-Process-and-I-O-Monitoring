import os
import sys

# Ensure the cyber_log_analyzer root is on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from src.web_dashboard import create_app

# WSGI Application entrypoint for Vercel Serverless Functions
app = create_app()
