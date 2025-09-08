from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID
from typing import List, Dict

class Transaction(BaseModel):
    user_id: Optional[UUID] = None
    amount: float
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    payment_method: Optional[str] = None
    transaction_type: str  # 'income' or 'expense'
    transaction_date: Optional[date] = None

class FinanceDeps(BaseModel):
    user_id: str
    user_name: str
    phone_number: str
    categories: List[Dict]
    credit_cards: List[Dict] = []
    recent_transactions: List[Dict] = []
