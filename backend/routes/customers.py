from fastapi import APIRouter, Depends, HTTPException, Query
from ..auth import require_roles
from ..database import IntegrityError, get_db
from ..schemas import CustomerCreate, CustomerUpdate, TierUpdate
from ..services.customer_service import create_customer,list_customers,get_customer,customer_view,update_customer,update_tier

router=APIRouter(prefix='/customers',tags=['Customers'])

@router.post('',status_code=201)
def create(p:CustomerCreate,user:dict=Depends(require_roles('administrator','field_officer'))):
    with get_db() as conn:return create_customer(conn,p,user['id'])

@router.get('')
def list_all(q:str|None=Query(default=None),user:dict=Depends(require_roles('administrator','field_officer'))):
    owner=user['id'] if user['role']=='field_officer' else None
    with get_db() as conn:return list_customers(conn,q,owner)

@router.get('/me')
def my_profile(user:dict=Depends(require_roles('customer'))):
    with get_db() as conn:
        customer=customer_view(conn,user['customer_id'])
        if not customer:raise HTTPException(404,'Customer profile not found')
        return customer

@router.get('/{customer_id}')
def get(customer_id:str,user:dict=Depends(require_roles('administrator','field_officer'))):
    with get_db() as conn:
        if user['role']=='field_officer':
            owner=conn.execute('SELECT created_by FROM customers WHERE id=?',(customer_id,)).fetchone()
            if not owner or owner['created_by']!=user['id']:
                raise HTTPException(404,'Customer not found')
            return get_customer(conn,customer_id)
        x=customer_view(conn,customer_id)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.patch('/{customer_id}',dependencies=[Depends(require_roles('administrator'))])
def update(customer_id:str,p:CustomerUpdate):
    with get_db() as conn:
        x=update_customer(conn,customer_id,p)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.patch('/{customer_id}/tier',dependencies=[Depends(require_roles('administrator'))])
def tier(customer_id:str,p:TierUpdate):
    with get_db() as conn:
        x=update_tier(conn,customer_id,p)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.delete('/{customer_id}', status_code=204,dependencies=[Depends(require_roles('administrator'))])
def delete(customer_id: str):
    with get_db() as conn:
        existing = get_customer(conn, customer_id)
        if not existing:
            raise HTTPException(404, 'Customer not found')
        try:
            conn.execute('DELETE FROM customers WHERE id=?', (customer_id,))
            conn.commit()
        except IntegrityError:
            conn.rollback()
            raise HTTPException(409, 'Customer cannot be removed because invoices or payments are linked to this customer')

@router.get('/{customer_id}/history',dependencies=[Depends(require_roles('administrator'))])
def history(customer_id:str):
    with get_db() as conn:
        customer=get_customer(conn,customer_id)
        if not customer:raise HTTPException(404,'Customer not found')
        from ..services.invoice_service import list_invoices
        return {'customer':customer,'invoices':list_invoices(conn,customer_id=customer_id)}
