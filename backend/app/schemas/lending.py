from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class LendingBase(BaseModel):
    borrower_name: str
    borrower_contact: Optional[str] = None
    expected_return_date: Optional[date] = None
    notes: Optional[str] = None


class LendingCreate(LendingBase):
    book_copy_id: int
    lent_date: Optional[date] = None  # Defaults to today


class LendingReturn(BaseModel):
    actual_return_date: Optional[date] = None  # Defaults to today


class LendingResponse(LendingBase):
    id: int
    book_copy_id: int
    lent_date: date
    actual_return_date: Optional[date] = None
    reminder_sent: bool = False
    is_active: bool = True
    is_overdue: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class OverdueLendingResponse(BaseModel):
    lending_id: int
    book_copy_id: int
    borrower_name: str
    borrower_contact: Optional[str] = None
    lent_date: str
    expected_return_date: str
    days_overdue: int
    reminder_sent: bool
