from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    tier: int = Field(ge=1, le=3)
    tier_reason: Optional[str] = Field(default=None, max_length=500)
    requested_deposit: Optional[float] = Field(default=None, ge=0)
    first_deposit_amount: Optional[float] = Field(default=None, ge=0)
    expected_payment_days: Optional[int] = Field(default=None, ge=0)

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    tier_reason: Optional[str] = Field(default=None, max_length=500)
    requested_deposit: Optional[float] = Field(default=None, ge=0)
    first_deposit_amount: Optional[float] = Field(default=None, ge=0)
    expected_payment_days: Optional[int] = Field(default=None, ge=0)

class TierUpdate(BaseModel):
    tier: int = Field(ge=1, le=3)
    tier_reason: Optional[str] = Field(default=None, max_length=500)
    requested_deposit: Optional[float] = Field(default=None, ge=0)
    first_deposit_amount: Optional[float] = Field(default=None, ge=0)
    expected_payment_days: Optional[int] = Field(default=None, ge=0)

class InvoiceCreate(BaseModel):
    customer_id: str
    invoice_number: str = Field(min_length=2, max_length=60)
    total_amount: float = Field(gt=0)
    due_date: Optional[date] = None

    @field_validator('invoice_number')
    @classmethod
    def clean_number(cls, v: str) -> str:
        return v.strip().upper()

class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: Optional[date] = None
    payment_method: Optional[str] = Field(default=None, max_length=40)
    reference: Optional[str] = Field(default=None, max_length=100)
