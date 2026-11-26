import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from ..database import now_iso
from ..schemas import ExpenseCreate
from .common import money


def create_expense(conn, payload: ExpenseCreate, recorded_by: str) -> dict:
    expense_id = str(uuid.uuid4())
    created_at = now_iso()
    expense_date = payload.expense_date.isoformat() if payload.expense_date else created_at[:10]
    conn.execute(
        '''INSERT INTO expenses
           (id,expense_date,category,description,amount,reference,recorded_by,created_at)
           VALUES(?,?,?,?,?,?,?,?)''',
        (expense_id, expense_date, payload.category, payload.description, money(payload.amount),
         payload.reference, recorded_by, created_at),
    )
    conn.commit()
    return dict(conn.execute('SELECT * FROM expenses WHERE id=?', (expense_id,)).fetchone())


def list_expenses(conn, start_date: date | None = None, end_date: date | None = None) -> list[dict]:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, 'start_date must be on or before end_date')
    sql = 'SELECT * FROM expenses WHERE 1=1'
    params = []
    if start_date:
        sql += ' AND expense_date>=?'
        params.append(start_date.isoformat())
    if end_date:
        sql += ' AND expense_date<=?'
        params.append(end_date.isoformat())
    sql += ' ORDER BY expense_date DESC,created_at DESC'
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def overdue_summary(conn, customer_id: str | None = None, created_by: str | None = None) -> dict:
    today = datetime.now(timezone.utc).date().isoformat()
    sql = '''SELECT COUNT(*) AS count,
                    COALESCE(SUM(i.total_amount-COALESCE(p.total_paid,0)),0) AS balance
             FROM invoices i
             LEFT JOIN (
               SELECT invoice_id,SUM(amount) AS total_paid FROM payments GROUP BY invoice_id
             ) p ON p.invoice_id=i.id
             WHERE i.due_date IS NOT NULL AND i.due_date<? AND i.total_amount>COALESCE(p.total_paid,0)'''
    params = [today]
    if customer_id:
        sql += ' AND i.customer_id=?'
        params.append(customer_id)
    if created_by:
        sql += ' AND EXISTS (SELECT 1 FROM customers c WHERE c.id=i.customer_id AND c.created_by=?)'
        params.append(created_by)
    row = conn.execute(sql, params).fetchone()
    return {'overdue_invoices': row['count'], 'overdue_balance': money(row['balance'])}


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _default_start(period: str, end: date) -> date:
    if period == 'daily':
        return end - timedelta(days=29)
    if period == 'weekly':
        current_monday = end - timedelta(days=end.weekday())
        return current_monday - timedelta(weeks=11)
    month_index = end.year * 12 + end.month - 1 - 11
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _bucket_key(period: str, value: date) -> str:
    if period == 'daily':
        return value.isoformat()
    if period == 'weekly':
        return (value - timedelta(days=value.weekday())).isoformat()
    return value.strftime('%Y-%m')


def _bucket_dates(period: str, start: date, end: date) -> list[str]:
    current = start
    if period == 'weekly':
        current -= timedelta(days=current.weekday())
    elif period == 'monthly':
        current = _month_start(current)
    keys = []
    while current <= end:
        keys.append(_bucket_key(period, current))
        if period == 'daily':
            current += timedelta(days=1)
        elif period == 'weekly':
            current += timedelta(weeks=1)
        else:
            month_index = current.year * 12 + current.month
            year, month = divmod(month_index, 12)
            current = date(year, month + 1, 1)
    return keys


def revenue_report(conn, period: str, start_date: date | None = None, end_date: date | None = None) -> dict:
    if period not in ('daily', 'weekly', 'monthly'):
        raise HTTPException(422, 'Period must be daily, weekly, or monthly')
    end = end_date or datetime.now(timezone.utc).date()
    start = start_date or _default_start(period, end)
    if start > end:
        raise HTTPException(422, 'start_date must be on or before end_date')
    if (end - start).days > 366:
        raise HTTPException(422, 'Report date range cannot exceed 366 days')

    buckets = {
        key: {'period': key, 'revenue': 0.0, 'payments': 0, 'expenses': 0.0, 'expense_count': 0}
        for key in _bucket_dates(period, start, end)
    }
    payment_rows = conn.execute(
        'SELECT payment_date,amount FROM payments WHERE payment_date>=? AND payment_date<=?',
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    for row in payment_rows:
        key = _bucket_key(period, date.fromisoformat(row['payment_date']))
        bucket = buckets.get(key)
        if bucket is not None:
            bucket['revenue'] = money(bucket['revenue'] + row['amount'])
            bucket['payments'] += 1

    expense_rows = conn.execute(
        'SELECT expense_date,amount FROM expenses WHERE expense_date>=? AND expense_date<=?',
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    for row in expense_rows:
        key = _bucket_key(period, date.fromisoformat(row['expense_date']))
        bucket = buckets.get(key)
        if bucket is not None:
            bucket['expenses'] = money(bucket['expenses'] + row['amount'])
            bucket['expense_count'] += 1

    groups = list(buckets.values())
    for bucket in groups:
        bucket['net_cash'] = money(bucket['revenue'] - bucket['expenses'])
    total_revenue = money(sum(bucket['revenue'] for bucket in groups))
    total_expenses = money(sum(bucket['expenses'] for bucket in groups))
    return {
        'period': period,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'total_revenue': total_revenue,
        'total_expenses': total_expenses,
        'net_cash': money(total_revenue - total_expenses),
        'payment_count': len(payment_rows),
        'expense_count': len(expense_rows),
        **overdue_summary(conn),
        'groups': groups,
    }


def executive_report(conn, period: str, start_date: date | None = None, end_date: date | None = None) -> dict:
    report = revenue_report(conn, period, start_date, end_date)
    start = date.fromisoformat(report['start_date'])
    end = date.fromisoformat(report['end_date'])

    acquisition = {group['period']: 0 for group in report['groups']}
    customer_rows = conn.execute(
        '''SELECT substr(created_at,1,10) AS created_date,COUNT(*) AS total
           FROM customers
           WHERE substr(created_at,1,10)>=? AND substr(created_at,1,10)<=?
           GROUP BY substr(created_at,1,10)''',
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    for row in customer_rows:
        key = _bucket_key(period, date.fromisoformat(row['created_date']))
        if key in acquisition:
            acquisition[key] += row['total']

    invoice_summary = conn.execute(
        '''SELECT COUNT(*) AS count,COALESCE(SUM(total_amount),0) AS total
           FROM invoices
           WHERE substr(created_at,1,10)>=? AND substr(created_at,1,10)<=?''',
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    top_lines = conn.execute(
        '''SELECT items.description,SUM(items.quantity) AS quantity,
                  SUM(items.line_total) AS total
           FROM invoice_items AS items
           JOIN invoices AS invoices ON invoices.id=items.invoice_id
           WHERE substr(invoices.created_at,1,10)>=?
             AND substr(invoices.created_at,1,10)<=?
             AND items.line_total>0
           GROUP BY items.description
           ORDER BY total DESC,items.description
           LIMIT 10''',
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    pending_submissions = conn.execute(
        "SELECT COUNT(*) AS count FROM payment_submissions WHERE status='pending'"
    ).fetchone()['count']

    return {
        **report,
        'invoices_issued': invoice_summary['count'],
        'invoice_value': money(invoice_summary['total']),
        'customer_acquisition': [
            {'period': period_key, 'customers': count}
            for period_key, count in acquisition.items()
        ],
        'top_invoice_lines': [
            {
                'description': row['description'],
                'quantity': float(row['quantity']),
                'total': money(row['total']),
            }
            for row in top_lines
        ],
        'pending_payment_submissions': pending_submissions,
    }
