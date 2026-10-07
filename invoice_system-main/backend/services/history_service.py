import uuid
from ..database import now_iso

def add_history(conn, invoice_id, event_type, description, amount=None, reference_id=None):
    conn.execute('''INSERT INTO invoice_history
        (id, invoice_id, event_type, description, amount, reference_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (str(uuid.uuid4()), invoice_id, event_type, description, amount, reference_id, now_iso()))

def get_history(conn, invoice_id):
    rows = conn.execute('''SELECT * FROM invoice_history
        WHERE invoice_id=? ORDER BY created_at DESC''', (invoice_id,)).fetchall()
    return [dict(r) for r in rows]
