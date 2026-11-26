from fastapi import APIRouter, Depends, HTTPException
from ..auth import authenticate, create_token, create_user, get_current_user, hash_password, public_user, require_admin, verify_password
from ..database import IntegrityError, get_db
from ..schemas import LoginRequest, PasswordChange, PasswordResetRequest, UserCreate

router = APIRouter(prefix='/auth', tags=['Auth'])


@router.post('/login')
def login(p: LoginRequest):
    with get_db() as conn:
        user = authenticate(conn, p.username.strip().lower(), p.password)
    if not user:
        raise HTTPException(401, 'Invalid username or password')
    return {'access_token': create_token(user), 'token_type': 'bearer', 'user': user}


@router.get('/me')
def me(user: dict = Depends(get_current_user)):
    return user


@router.get('/users', dependencies=[Depends(require_admin)])
def list_users():
    with get_db() as conn:
        rows = conn.execute('''SELECT users.id,users.username,users.role,users.customer_id,
                               users.created_at,users.must_change_password,
                               customers.name AS customer_name
                               FROM users LEFT JOIN customers ON customers.id=users.customer_id
                               ORDER BY users.created_at DESC''').fetchall()
        return [dict(row) for row in rows]


@router.post('/users', status_code=201, dependencies=[Depends(require_admin)])
def add_user(p: UserCreate):
    with get_db() as conn:
        try:
            return create_user(
                conn, p.username, p.password, p.role, p.customer_id,
                must_change_password=True,
            )
        except IntegrityError:
            conn.rollback()
            raise HTTPException(409, 'Username is already used or this customer already has a portal account')


@router.post('/users/{user_id}/password-reset')
def reset_user_password(
    user_id: str,
    payload: PasswordResetRequest,
    administrator: dict = Depends(require_admin),
):
    if user_id == administrator['id']:
        raise HTTPException(400, 'Use Change password to update your own password')
    with get_db() as conn:
        conn.lock_for_write('users', user_id)
        row = conn.execute('SELECT id FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'User not found')
        conn.execute(
            '''UPDATE users SET password_hash=?,must_change_password=1,
               token_version=token_version+1 WHERE id=?''',
            (hash_password(payload.temporary_password), user_id),
        )
        conn.commit()
        updated = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    return public_user(updated)


@router.post('/password/change')
def change_password(
    payload: PasswordChange,
    user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        conn.lock_for_write('users', user['id'])
        row = conn.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone()
        if not row:
            raise HTTPException(404, 'User not found')
        if not verify_password(payload.current_password, row['password_hash']):
            raise HTTPException(400, 'Current password is incorrect')
        conn.execute(
            '''UPDATE users SET password_hash=?,must_change_password=0,
               token_version=token_version+1 WHERE id=?''',
            (hash_password(payload.new_password), user['id']),
        )
        conn.commit()
        updated = public_user(conn.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone())
    return {
        'access_token': create_token(updated),
        'token_type': 'bearer',
        'user': updated,
    }
