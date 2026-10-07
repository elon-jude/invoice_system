from fastapi import APIRouter, HTTPException

from ..schemas import PaymentCalculatorRequest

router = APIRouter(prefix='/calculator', tags=['Calculator'])


@router.post('/estimate')
def estimate(payload: PaymentCalculatorRequest):
    total_cost = payload.construction_cost + payload.additional_cost
    if payload.discount > total_cost:
        raise HTTPException(400, 'The subsidy or discount cannot be greater than the total cost.')

    net_cost = max(0.0, total_cost - payload.discount)
    remaining_balance = max(0.0, net_cost - payload.amount_paid)

    return {
        'customer_name': payload.customer_name or '',
        'facility_type': payload.facility_type,
        'total_cost': round(total_cost, 2),
        'discount_amount': round(payload.discount, 2),
        'net_cost': round(net_cost, 2),
        'amount_paid': round(payload.amount_paid, 2),
        'remaining_balance': round(remaining_balance, 2),
        'note': 'The customer has no outstanding balance.' if remaining_balance == 0 else 'This is the remaining amount the customer needs to pay.'
    }
