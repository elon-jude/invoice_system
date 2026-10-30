from fastapi import APIRouter, HTTPException, Query
from ..database import get_db
from ..schemas import InvoiceCreate, PaymentCreate
from ..services.invoice_service import create_invoice,list_invoices,invoice_full,payments,record_payment
from ..services.history_service import get_history

router=APIRouter(prefix='/invoices',tags=['Invoices'])

@router.post('',status_code=201)
def create(p:InvoiceCreate):
    with get_db() as conn:return create_invoice(conn,p)

@router.get('')
def list_all(q:str|None=Query(default=None),status:str|None=Query(default=None),customer_id:str|None=Query(default=None)):
    with get_db() as conn:return list_invoices(conn,q,status,customer_id)

@router.get('/{invoice_id}')
def get(invoice_id:str):
    with get_db() as conn:
        x=invoice_full(conn,invoice_id)
        if not x:raise HTTPException(404,'Invoice not found')
        return x

@router.get('/{invoice_id}/history')
def history(invoice_id:str):
    with get_db() as conn:
        if not invoice_full(conn,invoice_id):raise HTTPException(404,'Invoice not found')
        return get_history(conn,invoice_id)

@router.post('/{invoice_id}/payments',status_code=201)
def payment(invoice_id:str,p:PaymentCreate):
    with get_db() as conn:return record_payment(conn,invoice_id,p)

@router.get('/{invoice_id}/payments')
def list_payment(invoice_id:str):
    with get_db() as conn:
        if not invoice_full(conn,invoice_id):raise HTTPException(404,'Invoice not found')
        return payments(conn,invoice_id)
