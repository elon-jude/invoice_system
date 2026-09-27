from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def money(value: float) -> float:
    return round(float(value or 0), 2)

def compute_status(total: float, paid: float) -> str:
    total, paid = money(total), money(paid)
    if paid <= 0: return 'NO_PAYMENT'
    if paid >= total: return 'FULLY_PAID'
    return 'PARTIALLY_PAID'
