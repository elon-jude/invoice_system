from fastapi import APIRouter
from ..database import get_db
from ..services.invoice_service import list_invoices

router=APIRouter(tags=['Dashboard'])

@router.get('/dashboard')
def dashboard():
    with get_db() as conn:
        customers=conn.execute('SELECT COUNT(*) n FROM customers').fetchone()['n']
        tiers={i:conn.execute('SELECT COUNT(*) n FROM customers WHERE tier=?',(i,)).fetchone()['n'] for i in (1,2,3)}
        invoices=list_invoices(conn)
        return {
          'total_customers':customers,
          'tier_1':tiers[1],'tier_2':tiers[2],'tier_3':tiers[3],
          'total_invoices':len(invoices),
          'fully_paid':sum(i['status']=='FULLY_PAID' for i in invoices),
          'partially_paid':sum(i['status']=='PARTIALLY_PAID' for i in invoices),
          'no_payment':sum(i['status']=='NO_PAYMENT' for i in invoices),
          'total_invoiced':round(sum(i['total_amount'] for i in invoices),2),
          'total_received':round(sum(i['total_paid'] for i in invoices),2),
          'outstanding':round(sum(i['outstanding_balance'] for i in invoices),2),
        }
