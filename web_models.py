"""
Modelos Pydantic para API REST do Sistema de Gestão Financeira
Sistema completo de autenticação com JWT, reset de senha e validações
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Literal
from datetime import datetime, date
from uuid import UUID
import re

# Modelos base de resposta
class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class PaginatedResponse(BaseModel):
    success: bool
    message: str
    data: List[dict]
    total: int
    page: int
    limit: int

# Modelos de autenticação
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    cpf: str = Field(..., pattern=r'^\d{11}$')

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    
    @validator('password')
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(None, pattern=r'^\+?[1-9]\d{1,14}$')

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    phone_number: str
    cpf: str
    is_active: bool
    onboarding_completed: bool
    role: Literal["user", "admin"]
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class RefreshToken(BaseModel):
    refresh_token: str

class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

# Modelos de categoria
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    category_type: str = Field(..., pattern=r'^(income|expense)$')
    description: Optional[str] = Field(None, max_length=200)
    is_active: bool = True

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    category_type: Optional[str] = Field(None, pattern=r'^(income|expense)$')
    description: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None

class CategoryResponse(BaseModel):
    id: UUID
    name: str
    category_type: str
    description: Optional[str]
    is_active: bool
    user_id: UUID
    created_at: datetime

# Modelos de cartão de crédito
class CreditCardCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    brand: Optional[str] = Field(None, max_length=30)
    credit_limit: Optional[float] = Field(None, ge=0)
    closing_day: int = Field(..., ge=1, le=31)
    due_day: int = Field(..., ge=1, le=31)
    is_active: bool = True

class CreditCardUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    brand: Optional[str] = Field(None, max_length=30)
    credit_limit: Optional[float] = Field(None, ge=0)
    closing_day: Optional[int] = Field(None, ge=1, le=31)
    due_day: Optional[int] = Field(None, ge=1, le=31)
    is_active: Optional[bool] = None

class CreditCardResponse(BaseModel):
    id: UUID
    name: str
    brand: Optional[str]
    credit_limit: Optional[float]
    closing_day: int
    due_day: int
    is_active: bool
    user_id: UUID
    created_at: datetime

# Modelos de transação
class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=200)
    category_id: UUID
    payment_method: str = Field(..., pattern=r'^(cash|debit|credit|pix|transfer)$')
    transaction_type: str = Field(..., pattern=r'^(income|expense)$')
    transaction_date: date
    credit_card_id: Optional[UUID] = None
    installments: Optional[int] = Field(None, ge=1, le=60)
    recurrence: bool = False
    due_date: Optional[date] = None

class TransactionUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    description: Optional[str] = Field(None, min_length=1, max_length=200)
    category_id: Optional[UUID] = None
    payment_method: Optional[str] = Field(None, pattern=r'^(cash|debit|credit|pix|transfer)$')
    transaction_date: Optional[date] = None
    credit_card_id: Optional[UUID] = None
    installments: Optional[int] = Field(None, ge=1, le=60)
    recurrence: Optional[bool] = None
    due_date: Optional[date] = None
    paid_date: Optional[date] = None

class TransactionResponse(BaseModel):
    id: UUID
    amount: float
    description: str
    category_id: UUID
    category_name: Optional[str]
    payment_method: str
    transaction_type: str
    transaction_date: date
    credit_card_id: Optional[UUID]
    credit_card_name: Optional[str]
    installments: Optional[int]
    recurrence: bool
    due_date: Optional[date]
    paid_date: Optional[date]
    user_id: UUID
    created_at: datetime

# Modelos de orçamento
class BudgetCreate(BaseModel):
    category_id: UUID
    budget_amount: float = Field(..., gt=0)
    period_type: str = Field(..., pattern=r'^(monthly|yearly)$')
    alert_50_percent: bool = True
    alert_75_percent: bool = True
    alert_90_percent: bool = True
    alert_100_percent: bool = True
    alert_over_budget: bool = True

class BudgetUpdate(BaseModel):
    budget_amount: Optional[float] = Field(None, gt=0)
    period_type: Optional[str] = Field(None, pattern=r'^(monthly|yearly)$')
    alert_50_percent: Optional[bool] = None
    alert_75_percent: Optional[bool] = None
    alert_90_percent: Optional[bool] = None
    alert_100_percent: Optional[bool] = None
    alert_over_budget: Optional[bool] = None
    is_active: Optional[bool] = None

class BudgetResponse(BaseModel):
    id: UUID
    category_id: UUID
    category_name: str
    budget_amount: float
    spent_amount: float
    remaining_amount: float
    percentage_used: float
    period_type: str
    alert_50_percent: bool
    alert_75_percent: bool
    alert_90_percent: bool
    alert_100_percent: bool
    alert_over_budget: bool
    is_active: bool
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

# Modelos de meta financeira
class FinancialGoalCreate(BaseModel):
    goal_name: str = Field(..., min_length=1, max_length=100)
    goal_type: str = Field(..., pattern=r'^(savings|investment|purchase|debt_payment)$')
    target_amount: float = Field(..., gt=0)
    target_date: date
    category_id: Optional[UUID] = None
    current_amount: float = Field(0, ge=0)

class FinancialGoalUpdate(BaseModel):
    goal_name: Optional[str] = Field(None, min_length=1, max_length=100)
    goal_type: Optional[str] = Field(None, pattern=r'^(savings|investment|purchase|debt_payment)$')
    target_amount: Optional[float] = Field(None, gt=0)
    target_date: Optional[date] = None
    category_id: Optional[UUID] = None
    current_amount: Optional[float] = Field(None, ge=0)
    is_completed: Optional[bool] = None
    is_active: Optional[bool] = None

class FinancialGoalResponse(BaseModel):
    id: UUID
    goal_name: str
    goal_type: str
    target_amount: float
    current_amount: float
    target_date: date
    category_id: Optional[UUID]
    category_name: Optional[str]
    progress_percentage: float
    is_completed: bool
    is_active: bool
    user_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

# Modelos de dashboards e relatórios
class DashboardData(BaseModel):
    total_income: float
    total_expenses: float
    balance: float
    monthly_income: float
    monthly_expenses: float
    monthly_balance: float
    categories_summary: List[dict]
    recent_transactions: List[TransactionResponse]
    budget_alerts: List[dict]
    goals_progress: List[dict]

class CategorySummary(BaseModel):
    category_id: UUID
    category_name: str
    category_type: str
    total_amount: float
    transaction_count: int
    budget_amount: Optional[float]
    budget_used_percentage: Optional[float]

# Filtros para consultas
class TransactionFilters(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    category_id: Optional[UUID] = None
    payment_method: Optional[str] = None
    transaction_type: Optional[str] = None
    credit_card_id: Optional[UUID] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None

class ReportFilters(BaseModel):
    start_date: date
    end_date: date
    category_ids: Optional[List[UUID]] = None
    transaction_type: Optional[str] = None
    group_by: str = Field("month", pattern=r'^(day|week|month|year|category)$')