from fastapi import APIRouter, Depends, HTTPException
from ..auth import get_current_user
from ..database import get_db
from ..services.invoice_service import list_invoices
from ..services.finance_service import overdue_summary

router=APIRouter(tags=['Dashboard'])

@router.get('/dashboard')
def dashboard(user:dict=Depends(get_current_user)):
    with get_db() as conn:
        role=user['role']
        if role=='field_officer':
            customers=conn.execute('SELECT COUNT(*) AS n FROM customers WHERE created_by=?',(user['id'],)).fetchone()['n']
            return {'role':role,'total_customers':customers,**overdue_summary(conn,created_by=user['id'])}
        if role=='customer':
            customer=conn.execute('SELECT name FROM customers WHERE id=?',(user['customer_id'],)).fetchone()
            if not customer:
                raise HTTPException(404,'Customer profile not found')
            invoices=list_invoices(conn,customer_id=user['customer_id'])
            return {
              'role':role,
              'customer_name':customer['name'],
              'total_invoices':len(invoices),
              'fully_paid':sum(i['status']=='FULLY_PAID' for i in invoices),
              'partially_paid':sum(i['status']=='PARTIALLY_PAID' for i in invoices),
              'no_payment':sum(i['status']=='NO_PAYMENT' for i in invoices),
              'total_invoiced':round(sum(i['total_amount'] for i in invoices),2),
              'total_received':round(sum(i['total_paid'] for i in invoices),2),
              'outstanding':round(sum(i['outstanding_balance'] for i in invoices),2),
              **overdue_summary(conn,customer_id=user['customer_id']),
            }
        if role not in ('administrator','ceo'):
            raise HTTPException(403,'This account does not have permission to view this dashboard')
        customers=conn.execute('SELECT COUNT(*) AS n FROM customers').fetchone()['n']
        tiers={i:conn.execute('SELECT COUNT(*) AS n FROM customers WHERE tier=?',(i,)).fetchone()['n'] for i in (1,2,3)}
        invoices=list_invoices(conn)
        total_expenses=conn.execute('SELECT COALESCE(SUM(amount),0) AS total FROM expenses').fetchone()['total']
        return {
          'role':role,
          'total_customers':customers,
          'tier_1':tiers[1],'tier_2':tiers[2],'tier_3':tiers[3],
          'total_invoices':len(invoices),
          'fully_paid':sum(i['status']=='FULLY_PAID' for i in invoices),
          'partially_paid':sum(i['status']=='PARTIALLY_PAID' for i in invoices),
          'no_payment':sum(i['status']=='NO_PAYMENT' for i in invoices),
          'total_invoiced':round(sum(i['total_amount'] for i in invoices),2),
          'total_received':round(sum(i['total_paid'] for i in invoices),2),
          'outstanding':round(sum(i['outstanding_balance'] for i in invoices),2),
          'total_expenses':round(float(total_expenses),2),
          'net_cash':round(sum(i['total_paid'] for i in invoices)-float(total_expenses),2),
          **overdue_summary(conn),
          'total_users':conn.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n'] if role=='administrator' else None,
        }
