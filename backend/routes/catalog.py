from typing import Literal
from fastapi import APIRouter, Depends, Query
from ..auth import require_roles
from ..database import get_db
from ..schemas import CatalogCreate, CatalogUpdate
from ..services.catalog_service import create_item, list_items, update_item

router=APIRouter(prefix='/catalog',tags=['Catalog'])

@router.get('')
def list_all(kind:Literal['facility','equipment']|None=Query(default=None),include_inactive:bool=Query(default=False),
             user:dict=Depends(require_roles('administrator','field_officer'))):
    if user['role']=='field_officer':
        include_inactive=False
    with get_db() as conn:return list_items(conn,kind,include_inactive)

@router.post('',status_code=201,dependencies=[Depends(require_roles('administrator'))])
def create(p:CatalogCreate):
    with get_db() as conn:return create_item(conn,p)

@router.patch('/{item_id}',dependencies=[Depends(require_roles('administrator'))])
def update(item_id:str,p:CatalogUpdate):
    with get_db() as conn:return update_item(conn,item_id,p)
