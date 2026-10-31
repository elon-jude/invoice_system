from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

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

    @field_validator('name')
    @classmethod
    def name_not_null(cls, v: Optional[str]) -> str:
        if v is None:
            raise ValueError('name cannot be null')
        return v.strip()

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
    initial_deposit: Optional[float] = Field(default=None, gt=0)
    deposit_method: Optional[str] = Field(default=None, max_length=40)

    @field_validator('invoice_number')
    @classmethod
    def clean_number(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode='after')
    def deposit_within_total(self):
        if self.initial_deposit is not None and self.initial_deposit > self.total_amount:
            raise ValueError('initial_deposit cannot exceed total_amount')
        return self

class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    payment_date: Optional[date] = None
    payment_method: Optional[str] = Field(default=None, max_length=40)
    reference: Optional[str] = Field(default=None, max_length=100)

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=200)

    @field_validator('username')
    @classmethod
    def clean_username(cls, v: str) -> str:
        return v.strip().lower()

class EquipmentLine(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    quantity: int = Field(default=1, ge=1, le=999)

class CalculatorRequest(BaseModel):
    customer_id: Optional[str] = None
    customer_name: Optional[str] = Field(default=None, max_length=120)
    facility_type: str = Field(default='', max_length=60)
    # Leave empty to use the price list amount for the facility.
    construction_cost: Optional[float] = Field(default=None, ge=0)
    equipment: list[EquipmentLine] = Field(default_factory=list, max_length=50)
    additional_cost: float = Field(default=0, ge=0)
    discount: float = Field(default=0, ge=0)
    amount_paid: float = Field(default=0, ge=0)
    installment_months: Optional[int] = Field(default=None, ge=1, le=60)

class CalculatorInvoiceRequest(CalculatorRequest):
    customer_id: str
    invoice_number: str = Field(min_length=2, max_length=60)
    due_date: Optional[date] = None
    deposit_method: Optional[str] = Field(default=None, max_length=40)

    @field_validator('invoice_number')
    @classmethod
    def clean_number(cls, v: str) -> str:
        return v.strip().upper()

class CatalogCreate(BaseModel):
    kind: Literal['facility', 'equipment']
    name: str = Field(min_length=2, max_length=80)
    price: float = Field(ge=0)

class CatalogUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    price: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None
