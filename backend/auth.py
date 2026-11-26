import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import ADMIN_PASSWORD, ADMIN_PASSWORD_RESET, ADMIN_USERNAME, AUTH_DISABLED, AUTH_DISABLED_REQUESTED, JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from .database import IntegrityError, get_db, now_iso

log = logging.getLogger(__name__)

if JWT_SECRET:
    SECRET = JWT_SECRET
else:
    SECRET = secrets.token_urlsafe(48)
    log.warning('JWT_SECRET is not set; using a random secret. Tokens will stop working on restart.')

if AUTH_DISABLED:
    log.warning('AUTH_DISABLED is on: login is skipped and ALL endpoints are open. Development only.')
elif AUTH_DISABLED_REQUESTED:
    log.error('AUTH_DISABLED was requested outside development/test; authentication remains enabled.')

PBKDF2_ITERATIONS = 600_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split('$')
        iterations = int(iterations)
        salt_bytes = bytes.fromhex(salt)
        bytes.fromhex(digest)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), salt_bytes, iterations)
    return hmac.compare_digest(candidate.hex(), digest)


def public_user(row) -> dict:
    user = {'id': row['id'], 'username': row['username'], 'role': row['role'], 'created_at': row['created_at']}
    if 'customer_id' in row.keys():
        user['customer_id'] = row['customer_id']
    if 'must_change_password' in row.keys():
        user['must_change_password'] = bool(row['must_change_password'])
    if 'token_version' in row.keys():
        user['token_version'] = row['token_version']
    return user


def create_user(
    conn,
    username: str,
    password: str,
    role: str = 'field_officer',
    customer_id: str | None = None,
    must_change_password: bool = False,
) -> dict:
    if role == 'customer':
        if not customer_id:
            raise HTTPException(400, 'A customer account must be linked to a customer profile')
        if not conn.execute('SELECT id FROM customers WHERE id=?', (customer_id,)).fetchone():
            raise HTTPException(404, 'Customer profile not found')
    elif customer_id:
        raise HTTPException(400, 'Only customer accounts can be linked to a customer profile')
    uid = str(uuid.uuid4())
    conn.execute('''INSERT INTO users
                    (id,username,password_hash,created_at,role,customer_id,must_change_password)
                    VALUES (?,?,?,?,?,?,?)''',
                 (uid, username, hash_password(password), now_iso(), role, customer_id, int(must_change_password)))
    conn.commit()
    return public_user(conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())


def authenticate(conn, username: str, password: str):
    row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    if row and verify_password(password, row['password_hash']):
        return public_user(row)
    return None


def create_token(user: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({
        'sub': user['id'],
        'username': user['username'],
        'ver': int(user.get('token_version', 0)),
        'exp': expires,
    }, SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if AUTH_DISABLED:
        return {
            'id': 'dev', 'username': 'dev', 'role': 'administrator',
            'customer_id': None, 'created_at': now_iso(),
            'must_change_password': False, 'token_version': 0,
        }
    unauthorized = HTTPException(401, 'Not authenticated', headers={'WWW-Authenticate': 'Bearer'})
    if not credentials:
        raise unauthorized
    try:
        payload = jwt.decode(credentials.credentials, SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized
    with get_db() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?', (payload.get('sub'),)).fetchone()
    if not row or int(payload.get('ver', 0)) != int(row['token_version']):
        raise unauthorized
    user = public_user(row)
    if user['must_change_password'] and request.url.path not in ('/auth/me', '/auth/password/change'):
        raise HTTPException(403, 'Password change required before continuing')
    return user


def require_roles(*roles: str):
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user.get('role') not in roles:
            raise HTTPException(403, 'This account does not have permission to access this resource')
        return user
    return dependency


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get('role') != 'administrator':
        raise HTTPException(403, 'Administrator role required')
    return user


def ensure_admin() -> None:
    """Create or explicitly reset the configured administrator account."""
    username = ADMIN_USERNAME.lower()
    if ADMIN_PASSWORD_RESET:
        if not username or len(ADMIN_PASSWORD) < 8:
            raise RuntimeError(
                'ADMIN_PASSWORD_RESET requires ADMIN_USERNAME and an ADMIN_PASSWORD of at least 8 characters'
            )

        with get_db() as conn:
            row = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
            if not row:
                try:
                    create_user(conn, username, ADMIN_PASSWORD, 'administrator', must_change_password=True)
                except IntegrityError:
                    conn.rollback()
                    row = conn.execute(
                        'SELECT id FROM users WHERE username=?', (username,)
                    ).fetchone()
                    if not row:
                        raise
                    conn.execute(
                        '''UPDATE users SET password_hash=?,role=?,must_change_password=1,
                           token_version=token_version+1 WHERE id=?''',
                        (hash_password(ADMIN_PASSWORD), 'administrator', row['id']),
                    )
                    conn.commit()
                log.warning('Created configured admin user %r', username)
            else:
                conn.execute(
                    '''UPDATE users SET password_hash=?,role=?,must_change_password=1,
                       token_version=token_version+1 WHERE id=?''',
                    (hash_password(ADMIN_PASSWORD), 'administrator', row['id']),
                )
                conn.commit()
                log.warning('Reset password for configured admin user %r', username)
        return

    with get_db() as conn:
        count = conn.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n']
        if ADMIN_USERNAME and len(ADMIN_PASSWORD) >= 8:
            row = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
            if row:
                conn.execute('UPDATE users SET role=? WHERE id=?', ('administrator', row['id']))
                conn.commit()
            elif count == 0:
                create_user(conn, username, ADMIN_PASSWORD, 'administrator', must_change_password=True)
                log.warning('Created initial admin user %r', username)
        elif not count:
            log.warning('No users exist. Set ADMIN_USERNAME and ADMIN_PASSWORD (8+ chars) and restart to create one.')
