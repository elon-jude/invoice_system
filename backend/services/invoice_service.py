import uuid
from fastapi import HTTPException
from ..database import now_iso
from .common import money, compute_status
from .history_service import add_history, get_history

def calculate_invoice(conn, invoice_id):
    row=conn.execute('SELECT * FROM invoices WHERE id=?',(invoice_id,)).fetchone()
    if not row:return None
    item=dict(row)
    paid=conn.execute('SELECT COALESCE(SUM(amount),0) total FROM payments WHERE invoice_id=?',(invoice_id,)).fetchone()['total']
    item['total_amount']=money(item['total_amount']);item['total_paid']=money(paid);item['outstanding_balance']=money(item['total_amount']-item['total_paid'])
    item['status']=compute_status(item['total_amount'],item['total_paid'])
    return item

def payments(conn,invoice_id):
    rows=conn.execute('SELECT * FROM payments WHERE invoice_id=? ORDER BY payment_date DESC,created_at DESC',(invoice_id,)).fetchall()
    return [dict(r) for r in rows]

def invoice_full(conn,invoice_id):
    inv=calculate_invoice(conn,invoice_id)
    if not inv:return None
    customer=conn.execute('SELECT * FROM customers WHERE id=?',(inv['customer_id'],)).fetchone()
    inv['customer']=dict(customer) if customer else None
    inv['payments']=payments(conn,invoice_id)
    inv['history']=get_history(conn,invoice_id)
    return inv

def create_invoice(conn,p):
    customer=conn.execute('SELECT id FROM customers WHERE id=?',(p.customer_id,)).fetchone()
    if not customer: raise HTTPException(404,'Customer not found')
    if conn.execute('SELECT id FROM invoices WHERE invoice_number=?',(p.invoice_number,)).fetchone(): raise HTTPException(409,'Invoice number already exists')
    iid=str(uuid.uuid4());now=now_iso()
    conn.execute('''INSERT INTO invoices(id,customer_id,invoice_number,total_amount,due_date,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
      (iid,p.customer_id,p.invoice_number,money(p.total_amount),p.due_date.isoformat() if p.due_date else None,'NO_PAYMENT',now,now))
    add_history(conn,iid,'INVOICE_CREATED',f'Invoice {p.invoice_number} was created.',money(p.total_amount),p.invoice_number)
    conn.commit();return invoice_full(conn,iid)

def list_invoices(conn,q=None,status=None,customer_id=None):
    sql='SELECT * FROM invoices WHERE 1=1';params=[]
    if q:sql+=' AND invoice_number LIKE ?';params.append(f'%{q}%')
    if status:sql+=' AND status=?';params.append(status)
    if customer_id:sql+=' AND customer_id=?';params.append(customer_id)
    sql+=' ORDER BY created_at DESC'
    rows=conn.execute(sql,params).fetchall();return [calculate_invoice(conn,r['id']) for r in rows]

def record_payment(conn,invoice_id,p):
    inv=calculate_invoice(conn,invoice_id)
    if not inv:raise HTTPException(404,'Invoice not found')
    amount=money(p.amount)
    if amount > inv['outstanding_balance'] + 0.009:raise HTTPException(400,f'Payment exceeds outstanding balance of {inv["outstanding_balance"]:.2f}')
    pid=str(uuid.uuid4());payment_date=(p.payment_date.isoformat() if p.payment_date else now_iso()[:10])
    conn.execute('''INSERT INTO payments(id,invoice_id,amount,payment_date,payment_method,reference,created_at) VALUES(?,?,?,?,?,?,?)''',
      (pid,invoice_id,amount,payment_date,p.payment_method,p.reference,now_iso()))
    new_paid=money(inv['total_paid']+amount);new_status=compute_status(inv['total_amount'],new_paid)
    conn.execute('UPDATE invoices SET status=?,updated_at=? WHERE id=?',(new_status,now_iso(),invoice_id))
    add_history(conn,invoice_id,'PAYMENT_RECORDED',f'Payment of GHS {amount:,.2f} was recorded.',amount,pid)
    if new_status=='FULLY_PAID':add_history(conn,invoice_id,'INVOICE_PAID',f'Invoice {inv["invoice_number"]} was fully paid.',amount,pid)
    conn.commit();return invoice_full(conn,invoice_id)
