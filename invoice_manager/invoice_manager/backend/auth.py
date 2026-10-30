import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ADMIN_PASSWORD, ADMIN_USERNAME, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from .database import get_db, now_iso

log = logging.getLogger(__name__)

if JWT_SECRET:
    SECRET = JWT_SECRET
else:
    SECRET = secrets.token_urlsafe(48)
    log.warning('JWT_SECRET is not set; using a random secret. Tokens will stop working on restart.')

PBKDF2_ITERATIONS = 600_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split('$')
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(candidate.hex(), digest)


def public_user(row) -> dict:
    return {'id': row['id'], 'username': row['username'], 'created_at': row['created_at']}


def create_user(conn, username: str, password: str) -> dict:
    uid = str(uuid.uuid4())
    conn.execute('INSERT INTO users (id,username,password_hash,created_at) VALUES (?,?,?,?)',
                 (uid, username, hash_password(password), now_iso()))
    conn.commit()
    return public_user(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())


def authenticate(conn, username: str, password: str):
    row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if row and verify_password(password, row['password_hash']):
        return public_user(row)
    return None


def create_token(user: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({'sub': user['id'], 'username': user['username'], 'exp': expires}, SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    unauthorized = HTTPException(401, 'Not authenticated', headers={'WWW-Authenticate': 'Bearer'})
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized
    with get_db() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?', (payload.get('sub'),)).fetchone()
    if not row:
        raise unauthorized
    return public_user(row)


def ensure_admin() -> None:
    """Create the first staff account from ADMIN_USERNAME/ADMIN_PASSWORD if no users exist."""
    with get_db() as conn:
        count = conn.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n']
        if count:
            return
        if ADMIN_USERNAME and len(ADMIN_PASSWORD) >= 8:
            create_user(conn, ADMIN_USERNAME.lower(), ADMIN_PASSWORD)
            log.warning('Created initial admin user %r', ADMIN_USERNAME.lower())
        else:
            log.warning('No users exist. Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ chars) and restart to create one.')
