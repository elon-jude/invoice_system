import re
import uuid
from fastapi import HTTPException
from ..database import IntegrityError, now_iso
from .common import money

# ESTIMATED starter prices (GHS). Edit them on the Price List page with real figures.
SEED = [
    ('facility', 'single', 'Eco Throne Toilet', 4500),
    ('facility', 'double', 'EcoFitron Toilet', 6500),
    ('facility', 'custom', 'NobleDuo Toilet', 8500),
    ('facility', 'mama', 'Mamaakiban Toilet', 5500),
    ('equipment', 'basin', 'Hand-wash basin', 350),
    ('equipment', 'waste-container', 'Waste container', 120),
    ('equipment', 'soap-dispenser', 'Soap dispenser', 90),
    ('equipment', 'water-tank', 'Water storage tank', 900),
    ('equipment', 'vent-pipe', 'Ventilation pipe kit', 150),
    ('equipment', 'tp-holder', 'Toilet paper holder', 40),
]

def _view(row):
    d = dict(row)
    d['price'] = money(d['price'])
    d['active'] = bool(d['active'])
    return d

def seed_catalog(conn):
    if conn.execute('SELECT COUNT(*) AS n FROM catalog_items').fetchone()['n']:
        return
    now = now_iso()
    for kind, code, name, price in SEED:
        conn.execute('INSERT INTO catalog_items(id,kind,code,name,price,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                     (str(uuid.uuid4()), kind, code, name, price, 1, now, now))
    conn.commit()

def list_items(conn, kind=None, include_inactive=False):
    sql = 'SELECT * FROM catalog_items WHERE 1=1'
    params = []
    if kind:
        sql += ' AND kind=?'; params.append(kind)
    if not include_inactive:
        sql += ' AND active=1'
    sql += ' ORDER BY kind, name'
    return [_view(r) for r in conn.execute(sql, params).fetchall()]

def get_by_code(conn, kind, code):
    row = conn.execute('SELECT * FROM catalog_items WHERE kind=? AND code=?', (kind, code)).fetchone()
    return _view(row) if row else None

def _new_code(conn, name):
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'item'
    code, n = base, 2
    while conn.execute('SELECT 1 FROM catalog_items WHERE code=?', (code,)).fetchone():
        code = f'{base}-{n}'; n += 1
    return code

def create_item(conn, p):
    iid, now = str(uuid.uuid4()), now_iso()
    try:
        conn.execute('INSERT INTO catalog_items(id,kind,code,name,price,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',
                     (iid, p.kind, _new_code(conn, p.name), p.name.strip(), money(p.price), 1, now, now))
        conn.commit()
    except IntegrityError:
        conn.rollback()
        raise HTTPException(409, 'An item with that name already exists')
    return _view(conn.execute('SELECT * FROM catalog_items WHERE id=?', (iid,)).fetchone())

def update_item(conn, item_id, p):
    row = conn.execute('SELECT * FROM catalog_items WHERE id=?', (item_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Item not found')
    data = {k: v for k, v in p.model_dump(exclude_unset=True).items() if v is not None}
    if 'name' in data: data['name'] = data['name'].strip()
    if 'price' in data: data['price'] = money(data['price'])
    if 'active' in data: data['active'] = 1 if data['active'] else 0
    if data:
        fields = [f'{k}=?' for k in data] + ['updated_at=?']
        conn.execute(f'UPDATE catalog_items SET {", ".join(fields)} WHERE id=?', [*data.values(), now_iso(), item_id])
        conn.commit()
    return _view(conn.execute('SELECT * FROM catalog_items WHERE id=?', (item_id,)).fetchone())
