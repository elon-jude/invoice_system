from fastapi import APIRouter
from ..database import get_db
from ..schemas import CalculatorInvoiceRequest, CalculatorRequest
from ..services.calculator_service import calculate_payment, create_invoice_from_calculation, next_invoice_number

router=APIRouter(prefix='/calculator',tags=['Calculator'])

@router.post('/calculate')
def calculate(p:CalculatorRequest):
    with get_db() as conn:return calculate_payment(conn,p)

@router.post('/invoice',status_code=201)
def invoice(p:CalculatorInvoiceRequest):
    with get_db() as conn:return create_invoice_from_calculation(conn,p)

@router.get('/next-invoice-number')
def next_number():
    with get_db() as conn:return {'invoice_number':next_invoice_number(conn)}
