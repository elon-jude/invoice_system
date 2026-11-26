from fastapi import APIRouter, Depends, HTTPException, Query
from ..auth import require_roles
from ..database import get_db
from ..schemas import InvoiceCreate, PaymentCreate, PaymentSubmissionReview
from ..services.invoice_service import (
    create_invoice,
    invoice_full,
    list_invoices,
    list_payment_submissions,
    payments,
    record_payment,
    reject_payment_submission,
    submit_payment,
    verify_payment_submission,
)
from ..services.history_service import get_history

router=APIRouter(prefix='/invoices',tags=['Invoices'])

@router.post('',status_code=201,dependencies=[Depends(require_roles('administrator'))])
def create(p:InvoiceCreate,user:dict=Depends(require_roles('administrator'))):
    with get_db() as conn:return create_invoice(conn,p,created_by=user['id'])

@router.get('')
def list_all(q:str|None=Query(default=None),status:str|None=Query(default=None),customer_id:str|None=Query(default=None),
             user:dict=Depends(require_roles('administrator','field_officer','customer'))):
    if user['role']=='customer':
        if customer_id and customer_id!=user['customer_id']:
            raise HTTPException(404,'Invoice not found')
        customer_id=user['customer_id']
    owner=user['id'] if user['role']=='field_officer' else None
    with get_db() as conn:return list_invoices(conn,q,status,customer_id,owner)

@router.get('/payment-submissions')
def get_payment_submissions(
    status:str|None=Query(default=None,pattern='^(pending|verified|rejected)$'),
    invoice_id:str|None=Query(default=None),
    user:dict=Depends(require_roles('administrator','field_officer')),
):
    with get_db() as conn:
        submitter=user['id'] if user['role']=='field_officer' else None
        return list_payment_submissions(conn,submitter,status,invoice_id)

@router.get('/{invoice_id}')
def get(invoice_id:str,user:dict=Depends(require_roles('administrator','field_officer','customer'))):
    with get_db() as conn:
        x=invoice_full(conn,invoice_id)
        if not x:raise HTTPException(404,'Invoice not found')
        if user['role']=='customer' and x['customer_id']!=user['customer_id']:
            raise HTTPException(404,'Invoice not found')
        if user['role']=='field_officer':
            owner=conn.execute('SELECT created_by FROM customers WHERE id=?',(x['customer_id'],)).fetchone()
            if not owner or owner['created_by']!=user['id']:
                raise HTTPException(404,'Invoice not found')
        if user['role']!='administrator':
            x.pop('history',None)
        return x

@router.get('/{invoice_id}/history',dependencies=[Depends(require_roles('administrator'))])
def history(invoice_id:str):
    with get_db() as conn:
        if not invoice_full(conn,invoice_id):raise HTTPException(404,'Invoice not found')
        return get_history(conn,invoice_id)

@router.post('/{invoice_id}/payments',status_code=201,dependencies=[Depends(require_roles('administrator'))])
def payment(invoice_id:str,p:PaymentCreate):
    with get_db() as conn:return record_payment(conn,invoice_id,p)

@router.get('/{invoice_id}/payments')
def list_payment(invoice_id:str,user:dict=Depends(require_roles('administrator','field_officer','customer'))):
    with get_db() as conn:
        invoice=invoice_full(conn,invoice_id)
        if not invoice:raise HTTPException(404,'Invoice not found')
        if user['role']=='customer' and invoice['customer_id']!=user['customer_id']:
            raise HTTPException(404,'Invoice not found')
        if user['role']=='field_officer':
            owner=conn.execute('SELECT created_by FROM customers WHERE id=?',(invoice['customer_id'],)).fetchone()
            if not owner or owner['created_by']!=user['id']:
                raise HTTPException(404,'Invoice not found')
        return payments(conn,invoice_id)


@router.post('/{invoice_id}/payment-submissions',status_code=201)
def submit_invoice_payment(
    invoice_id:str,
    payload:PaymentCreate,
    user:dict=Depends(require_roles('field_officer')),
):
    with get_db() as conn:
        owner=conn.execute(
            '''SELECT c.created_by FROM invoices i JOIN customers c ON c.id=i.customer_id
               WHERE i.id=?''',(invoice_id,),
        ).fetchone()
        if not owner or owner['created_by']!=user['id']:
            raise HTTPException(404,'Invoice not found')
        return submit_payment(conn,invoice_id,payload,user['id'])


@router.post('/payment-submissions/{submission_id}/verify')
def verify_submission(
    submission_id:str,
    user:dict=Depends(require_roles('administrator')),
):
    with get_db() as conn:
        return verify_payment_submission(conn,submission_id,user['id'])


@router.post('/payment-submissions/{submission_id}/reject')
def reject_submission(
    submission_id:str,
    payload:PaymentSubmissionReview,
    user:dict=Depends(require_roles('administrator')),
):
    with get_db() as conn:
        return reject_payment_submission(conn,submission_id,user['id'],payload.reason)
