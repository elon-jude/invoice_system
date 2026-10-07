from fastapi import APIRouter, Depends, HTTPException
from ..auth import authenticate, create_token, create_user, get_current_user
from ..database import IntegrityError, get_db
from ..schemas import LoginRequest, UserCreate

router=APIRouter(prefix='/auth',tags=['Auth'])

@router.post('/login')
def login(p:LoginRequest):
    with get_db() as conn:
        user=authenticate(conn,p.username.strip().lower(),p.password)
    if not user:raise HTTPException(401,'Invalid username or password')
    return {'access_token':create_token(user),'token_type':'bearer','user':user}

@router.get('/me')
def me(user:dict=Depends(get_current_user)):
    return user

@router.post('/users',status_code=201)
def add_user(p:UserCreate,user:dict=Depends(get_current_user)):
    with get_db() as conn:
        try:return create_user(conn,p.username,p.password)
        except IntegrityError:
            conn.rollback()
            raise HTTPException(409,'Username already exists')
