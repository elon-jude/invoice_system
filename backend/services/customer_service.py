import uuid
from ..database import now_iso

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

def list_customers(conn,q=None):
    if q:
        rows=conn.execute('SELECT * FROM customers WHERE name LIKE ? OR phone LIKE ? ORDER BY created_at DESC',(f'%{q}%',f'%{q}%')).fetchall()
    else: rows=conn.execute('SELECT * FROM customers ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows]

def update_customer(conn,cid,p):
    existing=get_customer(conn,cid)
    if not existing:return None
    data=p.model_dump(exclude_unset=True)
    if not data:return existing
    fields=[]; values=[]
    for k,v in data.items(): fields.append(f'{k}=?'); values.append(v)
    fields.append('updated_at=?'); values.append(now_iso()); values.append(cid)
    conn.execute(f'UPDATE customers SET {", ".join(fields)} WHERE id=?',values);conn.commit()
    return get_customer(conn,cid)

def update_tier(conn,cid,p):
    existing=get_customer(conn,cid)
    if not existing:return None
    conn.execute('''UPDATE customers SET tier=?,tier_reason=?,requested_deposit=?,first_deposit_amount=?,expected_payment_days=?,updated_at=? WHERE id=?''',
                 (p.tier,p.tier_reason,p.requested_deposit,p.first_deposit_amount,p.expected_payment_days,now_iso(),cid));conn.commit()
    return get_customer(conn,cid)
