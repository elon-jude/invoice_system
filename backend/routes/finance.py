from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..auth import require_roles
from ..database import get_db
from ..schemas import ExpenseCreate
from ..services.finance_service import create_expense, executive_report, list_expenses, revenue_report

router = APIRouter(tags=['Finance'])


@router.get('/reports/revenue', dependencies=[Depends(require_roles('administrator', 'ceo'))])
def get_revenue_report(
    period: Literal['daily', 'weekly', 'monthly'] = Query(default='daily'),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    with get_db() as conn:
        return revenue_report(conn, period, start_date, end_date)


@router.get('/reports/executive', dependencies=[Depends(require_roles('administrator', 'ceo'))])
def get_executive_report(
    period: Literal['daily', 'weekly', 'monthly'] = Query(default='monthly'),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    with get_db() as conn:
        return executive_report(conn, period, start_date, end_date)


@router.get('/expenses', dependencies=[Depends(require_roles('administrator', 'ceo'))])
def get_expenses(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
):
    with get_db() as conn:
        return list_expenses(conn, start_date, end_date)


@router.post('/expenses', status_code=201)
def add_expense(
    payload: ExpenseCreate,
    user: dict = Depends(require_roles('administrator')),
):
    with get_db() as conn:
        return create_expense(conn, payload, user['id'])
