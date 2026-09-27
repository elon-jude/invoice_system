from fastapi import APIRouter, HTTPException, Query
from ..database import get_db
from ..schemas import CustomerCreate, CustomerUpdate, TierUpdate
from ..services.customer_service import create_customer,list_customers,get_customer,update_customer,update_tier

router=APIRouter(prefix='/customers',tags=['Customers'])

@router.post('',status_code=201)
def create(p:CustomerCreate):
    with get_db() as conn:return create_customer(conn,p)

@router.get('')
def list_all(q:str|None=Query(default=None)):
    with get_db() as conn:return list_customers(conn,q)

@router.get('/{customer_id}')
def get(customer_id:str):
    with get_db() as conn:
        x=get_customer(conn,customer_id)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.patch('/{customer_id}')
def update(customer_id:str,p:CustomerUpdate):
    with get_db() as conn:
        x=update_customer(conn,customer_id,p)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.patch('/{customer_id}/tier')
def tier(customer_id:str,p:TierUpdate):
    with get_db() as conn:
        x=update_tier(conn,customer_id,p)
        if not x:raise HTTPException(404,'Customer not found')
        return x

@router.delete('/{customer_id}', status_code=204)
def delete(customer_id: str):
    with get_db() as conn:
        existing = get_customer(conn, customer_id)
        if not existing:
            raise HTTPException(404, 'Customer not found')
        try:
            conn.execute('DELETE FROM customers WHERE id=?', (customer_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise HTTPException(409, 'Customer cannot be removed because invoices or payments are linked to this customer')

@router.get('/{customer_id}/history')
def history(customer_id:str):
    with get_db() as conn:
        customer=get_customer(conn,customer_id)
        if not customer:raise HTTPException(404,'Customer not found')
        from ..services.invoice_service import list_invoices
        return {'customer':customer,'invoices':list_invoices(conn,customer_id=customer_id)}
