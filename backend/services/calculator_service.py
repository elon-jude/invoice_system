from datetime import date
from decimal import Decimal, ROUND_FLOOR
from fastapi import HTTPException
from ..database import now_iso
from ..schemas import InvoiceCreate
from .catalog_service import get_by_code
from .common import money
from .invoice_service import create_invoice

def _installments(remaining, months):
    """Equal monthly amounts (no interest); the last one absorbs any cent difference."""
    if not months or remaining <= 0:
        return None
    rem = Decimal(str(remaining))
    base = (rem / months).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)
    final = rem - base * (months - 1)
    return {'months': months, 'monthly_amount': money(base), 'final_amount': money(final)}

def calculate_payment(conn, p):
    """Work out what a customer still has to pay for a toilet facility and its equipment."""
    facility = get_by_code(conn, 'facility', p.facility_type) if p.facility_type else None
    if not facility or not facility['active']:
        raise HTTPException(400, 'Please select the toilet facility type.')

    cost = money(p.construction_cost) if p.construction_cost else facility['price']
    if cost <= 0:
        raise HTTPException(400, 'Please enter the construction cost.')

    customer_name = (p.customer_name or '').strip() or None
    if p.customer_id:
        row = conn.execute('SELECT name FROM customers WHERE id=?', (p.customer_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Customer not found')
        customer_name = row['name']

    lines = [{'kind': 'facility', 'code': facility['code'], 'description': facility['name'],
              'quantity': 1, 'unit_price': cost, 'line_total': cost}]
    wanted = {}
    for e in p.equipment:
        wanted[e.code] = wanted.get(e.code, 0) + e.quantity
    for code, qty in wanted.items():
        item = get_by_code(conn, 'equipment', code)
        if not item or not item['active']:
            raise HTTPException(400, f'Unknown equipment item: {code}')
        lines.append({'kind': 'equipment', 'code': code, 'description': item['name'],
                      'quantity': qty, 'unit_price': item['price'], 'line_total': money(item['price'] * qty)})

    equipment_total = money(sum(l['line_total'] for l in lines[1:]))
    additional = money(p.additional_cost)
    total_cost = money(cost + equipment_total + additional)
    discount = money(p.discount)
    if discount > total_cost:
        raise HTTPException(400, 'The subsidy or discount cannot be greater than the total cost.')

    net_cost = money(max(0, total_cost - discount))
    amount_paid = money(p.amount_paid)
    remaining = money(max(0, net_cost - amount_paid))
    return {
        'customer_id': p.customer_id,
        'customer_name': customer_name,
        'facility_type': facility['code'],
        'facility_name': facility['name'],
        'lines': lines,
        'construction_cost': cost,
        'equipment_total': equipment_total,
        'additional_cost': additional,
        'total_cost': total_cost,
        'discount': discount,
        'net_cost': net_cost,
        'amount_paid': amount_paid,
        'remaining_balance': remaining,
        'overpaid': money(max(0, amount_paid - net_cost)),
        'fully_paid': remaining == 0,
        'installments': _installments(remaining, p.installment_months),
    }

def create_invoice_from_calculation(conn, p):
    """Issue a real invoice for the net customer cost, saving the calculation as its line items."""
    calc = calculate_payment(conn, p)
    net, paid = calc['net_cost'], calc['amount_paid']
    if net <= 0:
        raise HTTPException(400, 'Nothing to invoice: the net customer cost is 0.')
    if paid > net:
        raise HTTPException(400, 'Amount already paid cannot be more than the net customer cost.')
    items = list(calc['lines'])
    if calc['additional_cost']:
        items.append({'kind': 'additional', 'description': 'Additional costs', 'quantity': 1,
                      'unit_price': calc['additional_cost'], 'line_total': calc['additional_cost']})
    if calc['discount']:
        items.append({'kind': 'discount', 'description': 'Approved subsidy / discount', 'quantity': 1,
                      'unit_price': -calc['discount'], 'line_total': -calc['discount']})
    invoice = InvoiceCreate(customer_id=p.customer_id, invoice_number=p.invoice_number, total_amount=net,
                            due_date=p.due_date, initial_deposit=paid or None, deposit_method=p.deposit_method)
    return create_invoice(conn, invoice, items)

def next_invoice_number(conn):
    prefix = f'INV-{now_iso()[:4]}-'
    n = 0
    for r in conn.execute('SELECT invoice_number FROM invoices WHERE invoice_number LIKE ?', (prefix + '%',)).fetchall():
        suffix = r['invoice_number'][len(prefix):]
        if suffix.isdigit():
            n = max(n, int(suffix))
    return f'{prefix}{n + 1:04d}'
