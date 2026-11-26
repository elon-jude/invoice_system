from datetime import date
from typing import Literal, Optional
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
    invoice_number: Optional[str] = Field(default=None, min_length=2, max_length=60)
    total_amount: float = Field(gt=0)
    due_date: Optional[date] = None
    initial_deposit: Optional[float] = Field(default=None, gt=0)
    deposit_method: Optional[str] = Field(default=None, max_length=40)

    @field_validator('invoice_number')
    @classmethod
    def clean_number(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else None

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

class ExpenseCreate(BaseModel):
    expense_date: Optional[date] = None
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=2, max_length=300)
    amount: float = Field(gt=0)
    reference: Optional[str] = Field(default=None, max_length=100)

    @field_validator('category', 'description')
    @classmethod
    def clean_expense_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('value cannot be blank')
        return cleaned

class PaymentSubmissionReview(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)

    @model_validator(mode='after')
    def require_new_password(self):
        if self.current_password == self.new_password:
            raise ValueError('The new password must be different from the current password')
        return self

class PasswordResetRequest(BaseModel):
    temporary_password: str = Field(min_length=8, max_length=200)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=8, max_length=200)
    role: Literal['ceo', 'administrator', 'field_officer', 'customer'] = 'field_officer'
    customer_id: Optional[str] = None

    @field_validator('username')
    @classmethod
    def clean_username(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode='after')
    def customer_role_requires_profile(self):
        if self.role == 'customer' and not self.customer_id:
            raise ValueError('customer_id is required for customer accounts')
        if self.role != 'customer' and self.customer_id:
            raise ValueError('customer_id is only valid for customer accounts')
        return self

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
    invoice_number: Optional[str] = Field(default=None, min_length=2, max_length=60)
    due_date: Optional[date] = None
    deposit_method: Optional[str] = Field(default=None, max_length=40)

    @field_validator('invoice_number')
    @classmethod
    def clean_number(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else None

class CatalogCreate(BaseModel):
    kind: Literal['facility', 'equipment']
    name: str = Field(min_length=2, max_length=80)
    price: float = Field(ge=0)

class CatalogUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    price: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None
    price_confirmed: Optional[bool] = None
