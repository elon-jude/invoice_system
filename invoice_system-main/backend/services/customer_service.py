import uuid
from ..database import now_iso
from .common import money

def create_customer(conn, p):
    cid = str(uuid.uuid4()); now = now_iso()
    conn.execute('''INSERT INTO customers
      (id,name,phone,tier,tier_reason,requested_deposit,first_deposit_amount,expected_payment_days,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?,?,?,?)''', (cid,p.name.strip(),p.phone,p.tier,p.tier_reason,p.requested_deposit,p.first_deposit_amount,p.expected_payment_days,now,now))
    conn.commit()
    return get_customer(conn,cid)

def get_customer(conn,cid):
    row=conn.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone()
    return dict(row) if row else None

def customer_view(conn,cid):
    """Customer record with every invoice, its balance and its payment history."""
    from .invoice_service import list_invoices, payments
    customer=get_customer(conn,cid)
    if not customer:return None
    invoices=list_invoices(conn,customer_id=cid)
    history=[]
    for inv in invoices:
        inv['payments']=payments(conn,inv['id'])
        history+=[{**pay,'invoice_number':inv['invoice_number']} for pay in inv['payments']]
    history.sort(key=lambda x:(x['payment_date'],x['created_at']),reverse=True)
    customer['invoices']=invoices
    customer['payment_history']=history
    customer['total_invoiced']=money(sum(i['total_amount'] for i in invoices))
    customer['total_paid']=money(sum(i['total_paid'] for i in invoices))
    customer['outstanding_balance']=money(sum(i['outstanding_balance'] for i in invoices))
    return customer

def list_customers(conn,q=None):
    if q:
        like=f'%{q.lower()}%'
        rows=conn.execute('SELECT * FROM customers WHERE LOWER(name) LIKE ? OR LOWER(phone) LIKE ? ORDER BY created_at DESC',(like,like)).fetchall()
    else: rows=conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows]

def _apply_update(conn,cid,data):
    fields=[]; values=[]
    for k,v in data.items(): fields.append(f'{k}=?'); values.append(v)
    fields.append('updated_at=?'); values.append(now_iso()); values.append(cid)
    conn.execute(f'UPDATE customers SET {", ".join(fields)} WHERE id=?',values);conn.commit()

def update_customer(conn,cid,p):
    existing=get_customer(conn,cid)
    if not existing:return None
    data=p.model_dump(exclude_unset=True)
    if not data:return existing
    _apply_update(conn,cid,data)
    return get_customer(conn,cid)

def update_tier(conn,cid,p):
    existing=get_customer(conn,cid)
    if not existing:return None
    # Only overwrite the assessment fields the caller actually sent.
    _apply_update(conn,cid,{**p.model_dump(exclude_unset=True),'tier':p.tier})
    return get_customer(conn,cid)
