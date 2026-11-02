import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'invoices.db'
APP_TITLE = 'WASHKING Invoice Management API'
APP_VERSION = '1.1.0'

# PostgreSQL connection string (e.g. postgresql://user:pass@host:5432/db).
# When unset, the local SQLite file at DB_PATH is used.
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()

# JWT signing secret. Must be set to a long random value in production so that
# tokens stay valid across restarts and across instances.
JWT_SECRET = os.getenv('JWT_SECRET', '').strip()
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_MINUTES = int(os.getenv('JWT_EXPIRE_MINUTES', '720'))

# First staff account, created on startup only when no users exist yet.
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', '').strip()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
ADMIN_PASSWORD_RESET = os.getenv('ADMIN_PASSWORD_RESET', '').strip().lower() in ('1', 'true', 'yes', 'on')

# DEV ONLY: set AUTH_DISABLED=1 to skip login so features can be tried without signing in.
# Every endpoint becomes open to anyone who can reach the server, so never use this in production.
AUTH_DISABLED = os.getenv('AUTH_DISABLED', '').strip().lower() in ('1', 'true', 'yes', 'on')
