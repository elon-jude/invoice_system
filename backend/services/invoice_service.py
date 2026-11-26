import uuid
from datetime import date
from fastapi import HTTPException
from ..database import IntegrityError, now_iso
from ..schemas import PaymentCreate
from .common import money, compute_status
from .history_service import add_history, get_history

def calculate_invoice(conn, invoice_id):
    row=conn.execute('SELECT * FROM invoices WHERE id=?',(invoice_id,)).fetchone()
    if not row:return None
    item=dict(row)
    paid=conn.execute('SELECT COALESCE(SUM(amount),0) AS total FROM payments WHERE invoice_id=?',(invoice_id,)).fetchone()['total']
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
    inv['items']=invoice_items(conn,invoice_id)
    return inv

def invoice_items(conn,invoice_id):
    rows=conn.execute('SELECT * FROM invoice_items WHERE invoice_id=? ORDER BY line_no',(invoice_id,)).fetchall()
    return [{**dict(r),'quantity':float(r['quantity']),'unit_price':money(r['unit_price']),'line_total':money(r['line_total'])} for r in rows]

def _insert_items(conn,invoice_id,items):
    """Save the lines an invoice was built from, at the prices used at the time. Caller commits."""
    for n,it in enumerate(items or [],1):
        conn.execute('INSERT INTO invoice_items(id,invoice_id,line_no,kind,description,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?,?)',
          (str(uuid.uuid4()),invoice_id,n,it['kind'],it['description'],it['quantity'],money(it['unit_price']),money(it['line_total'])))

def _insert_payment(conn,inv,amount,payment_date,payment_method,reference,label='Payment',actor_id=None):
    """Insert a payment, refresh the stored status and write history. Caller commits."""
    pid=str(uuid.uuid4())
    conn.execute('''INSERT INTO payments(id,invoice_id,amount,payment_date,payment_method,reference,created_at,recorded_by)
      VALUES(?,?,?,?,?,?,?,?)''',
      (pid,inv['id'],amount,payment_date,payment_method,reference,now_iso(),actor_id))
    new_paid=money(inv['total_paid']+amount);new_status=compute_status(inv['total_amount'],new_paid)
    conn.execute('UPDATE invoices SET status=?,updated_at=? WHERE id=?',(new_status,now_iso(),inv['id']))
    add_history(conn,inv['id'],'PAYMENT_RECORDED',f'{label} of GH₵ {amount:,.2f} was recorded.',amount,pid,actor_id)
    if new_status=='FULLY_PAID':add_history(conn,inv['id'],'INVOICE_PAID',f'Invoice {inv["invoice_number"]} was fully paid.',amount,pid,actor_id)

def next_invoice_number(conn):
    prefix = f'WK-{now_iso()[:4]}-'
    n = 0
    for row in conn.execute('SELECT invoice_number FROM invoices WHERE invoice_number LIKE ?', (prefix + '%',)).fetchall():
        suffix = row['invoice_number'][len(prefix):]
        if suffix.isdigit():
            n = max(n, int(suffix))
    return f'{prefix}{n + 1:04d}'

def create_invoice(conn,p,items=None,created_by=None):
    customer=conn.execute('SELECT id FROM customers WHERE id=?',(p.customer_id,)).fetchone()
    if not customer: raise HTTPException(404,'Customer not found')
    invoice_number = p.invoice_number
    if not invoice_number:
        conn.lock_for_invoice_number_generation()
        invoice_number = next_invoice_number(conn)
    if conn.execute('SELECT id FROM invoices WHERE invoice_number=?',(invoice_number,)).fetchone(): raise HTTPException(409,'Invoice number already exists')
    iid=str(uuid.uuid4());now=now_iso();total=money(p.total_amount)
    try:
        conn.execute('''INSERT INTO invoices(id,customer_id,invoice_number,total_amount,due_date,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)''',
          (iid,p.customer_id,invoice_number,total,p.due_date.isoformat() if p.due_date else None,'NO_PAYMENT',now,now))
    except IntegrityError:
        conn.rollback();raise HTTPException(409,'Invoice number already exists')
    add_history(conn,iid,'INVOICE_CREATED',f'Invoice {invoice_number} was created.',total,invoice_number,created_by)
    _insert_items(conn,iid,items)
    if p.initial_deposit:
        inv={'id':iid,'invoice_number':invoice_number,'total_amount':total,'total_paid':0.0}
        _insert_payment(conn,inv,money(p.initial_deposit),now[:10],p.deposit_method,'Initial deposit','Initial deposit',created_by)
    conn.commit();return invoice_full(conn,iid)

def list_invoices(conn,q=None,status=None,customer_id=None,created_by=None):
    sql='SELECT * FROM invoices WHERE 1=1';params=[]
    if created_by:
        sql+=' AND EXISTS (SELECT 1 FROM customers c WHERE c.id=invoices.customer_id AND c.created_by=?)'
        params.append(created_by)
    if q:sql+=' AND LOWER(invoice_number) LIKE ?';params.append(f'%{q.lower()}%')
    if status:sql+=' AND status=?';params.append(status)
    if customer_id:sql+=' AND customer_id=?';params.append(customer_id)
    sql+=' ORDER BY created_at DESC'
    rows=conn.execute(sql,params).fetchall();return [calculate_invoice(conn,r['id']) for r in rows]

def record_payment(conn,invoice_id,p,actor_id=None,commit=True):
    conn.lock_for_write('invoices',invoice_id)
    inv=calculate_invoice(conn,invoice_id)
    if not inv:raise HTTPException(404,'Invoice not found')
    amount=money(p.amount)
    if amount > inv['outstanding_balance'] + 0.009:raise HTTPException(400,f'Payment exceeds outstanding balance of {inv["outstanding_balance"]:.2f}')
    payment_date=(p.payment_date.isoformat() if p.payment_date else now_iso()[:10])
    _insert_payment(conn,inv,amount,payment_date,p.payment_method,p.reference,actor_id=actor_id)
    if commit:conn.commit()
    return invoice_full(conn,invoice_id)

def submit_payment(conn,invoice_id,p,submitted_by):
    conn.lock_for_write('invoices',invoice_id)
    inv=calculate_invoice(conn,invoice_id)
    if not inv:raise HTTPException(404,'Invoice not found')
    pending=conn.execute("SELECT COALESCE(SUM(amount),0) AS total FROM payment_submissions WHERE invoice_id=? AND status='pending'",(invoice_id,)).fetchone()['total']
    available=money(inv['outstanding_balance']-money(pending))
    amount=money(p.amount)
    if amount > available + 0.009:
        raise HTTPException(400,f'Payment submissions exceed the available outstanding balance of {available:.2f}')
    sid=str(uuid.uuid4());now=now_iso()
    payment_date=p.payment_date.isoformat() if p.payment_date else now[:10]
    conn.execute('''INSERT INTO payment_submissions
      (id,invoice_id,amount,payment_date,payment_method,reference,submitted_by,submitted_at,status)
      VALUES(?,?,?,?,?,?,?,?,'pending')''',
      (sid,invoice_id,amount,payment_date,p.payment_method,p.reference,submitted_by,now))
    add_history(conn,invoice_id,'PAYMENT_SUBMITTED',f'Payment submission of GH₵ {amount:,.2f} is awaiting verification.',amount,sid,submitted_by)
    conn.commit()
    return get_payment_submission(conn,sid)

def _submission_query(conn,submission_id=None,user_id=None,status=None,invoice_id=None):
    sql='''SELECT s.*,i.invoice_number,i.customer_id,c.name AS customer_name,
                  u.username AS submitter_username
           FROM payment_submissions s
           JOIN invoices i ON i.id=s.invoice_id
           JOIN customers c ON c.id=i.customer_id
           LEFT JOIN users u ON u.id=s.submitted_by
           WHERE 1=1'''
    params=[]
    for column,value in (('s.id',submission_id),('s.submitted_by',user_id),('s.status',status),('s.invoice_id',invoice_id)):
        if value is not None:
            sql+=f' AND {column}=?';params.append(value)
    return sql,params

def get_payment_submission(conn,submission_id):
    sql,params=_submission_query(conn,submission_id=submission_id)
    row=conn.execute(sql,params).fetchone()
    return dict(row) if row else None

def list_payment_submissions(conn,user_id=None,status=None,invoice_id=None):
    sql,params=_submission_query(conn,user_id=user_id,status=status,invoice_id=invoice_id)
    sql+=' ORDER BY s.submitted_at DESC'
    return [dict(row) for row in conn.execute(sql,params).fetchall()]

def verify_payment_submission(conn,submission_id,reviewed_by):
    conn.lock_for_write('payment_submissions',submission_id)
    submission=get_payment_submission(conn,submission_id)
    if not submission:raise HTTPException(404,'Payment submission not found')
    if submission['status']!='pending':raise HTTPException(409,'Payment submission has already been reviewed')
    payment=PaymentCreate(
        amount=float(submission['amount']),
        payment_date=date.fromisoformat(submission['payment_date']),
        payment_method=submission['payment_method'],
        reference=submission['reference'],
    )
    invoice=record_payment(conn,submission['invoice_id'],payment,actor_id=reviewed_by,commit=False)
    reviewed_at=now_iso()
    conn.execute("UPDATE payment_submissions SET status='verified',reviewed_by=?,reviewed_at=? WHERE id=?",
                 (reviewed_by,reviewed_at,submission_id))
    add_history(conn,submission['invoice_id'],'PAYMENT_SUBMISSION_VERIFIED',
                f'Payment submission of GH₵ {money(submission["amount"]):,.2f} was verified.',
                submission['amount'],submission_id,reviewed_by)
    conn.commit()
    return {'submission':get_payment_submission(conn,submission_id),'invoice':invoice}

def reject_payment_submission(conn,submission_id,reviewed_by,reason=None):
    conn.lock_for_write('payment_submissions',submission_id)
    submission=get_payment_submission(conn,submission_id)
    if not submission:raise HTTPException(404,'Payment submission not found')
    if submission['status']!='pending':raise HTTPException(409,'Payment submission has already been reviewed')
    note=reason or 'Rejected by administrator'
    conn.execute("UPDATE payment_submissions SET status='rejected',reviewed_by=?,reviewed_at=?,decision_note=? WHERE id=?",
                 (reviewed_by,now_iso(),note,submission_id))
    add_history(conn,submission['invoice_id'],'PAYMENT_SUBMISSION_REJECTED',
                f'Payment submission was rejected: {note}',submission['amount'],submission_id,reviewed_by)
    conn.commit()
    return get_payment_submission(conn,submission_id)
