from fastapi import APIRouter, Depends, HTTPException
from ..auth import require_roles
from ..database import get_db
from ..schemas import CalculatorInvoiceRequest, CalculatorRequest
from ..services.calculator_service import calculate_payment, create_invoice_from_calculation
from ..services.invoice_service import next_invoice_number

router=APIRouter(prefix='/calculator',tags=['Calculator'])

@router.post('/calculate')
def calculate(p:CalculatorRequest,user:dict=Depends(require_roles('administrator','field_officer'))):
    with get_db() as conn:
        if user['role']=='field_officer' and p.customer_id:
            owner=conn.execute('SELECT created_by FROM customers WHERE id=?',(p.customer_id,)).fetchone()
            if not owner or owner['created_by']!=user['id']:
                raise HTTPException(404,'Customer not found')
        return calculate_payment(conn,p)

@router.post('/invoice',status_code=201,dependencies=[Depends(require_roles('administrator'))])
def invoice(p:CalculatorInvoiceRequest,user:dict=Depends(require_roles('administrator'))):
    with get_db() as conn:return create_invoice_from_calculation(conn,p,user['id'])

@router.get('/next-invoice-number',dependencies=[Depends(require_roles('administrator'))])
def next_number():
    with get_db() as conn:return {'invoice_number':next_invoice_number(conn)}
