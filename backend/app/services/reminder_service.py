"""Lending reminder service - checks for overdue books and sends reminders."""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lending import Lending

logger = logging.getLogger(__name__)


async def get_overdue_lendings(db: AsyncSession) -> list[dict]:
    """Get all active lendings that are past their expected return date."""
    stmt = select(Lending).where(
        Lending.actual_return_date.is_(None),
        Lending.expected_return_date.isnot(None),
        Lending.expected_return_date < date.today(),
    )
    result = await db.execute(stmt)
    lendings = result.scalars().all()

    overdue = []
    for lending in lendings:
        days_overdue = (date.today() - lending.expected_return_date).days
        overdue.append({
            "lending_id": lending.id,
            "book_copy_id": lending.book_copy_id,
            "borrower_name": lending.borrower_name,
            "borrower_contact": lending.borrower_contact,
            "lent_date": lending.lent_date.isoformat(),
            "expected_return_date": lending.expected_return_date.isoformat(),
            "days_overdue": days_overdue,
            "reminder_sent": lending.reminder_sent,
        })

    return overdue


async def get_active_lendings(db: AsyncSession) -> list[dict]:
    """Get all currently active lendings."""
    stmt = select(Lending).where(Lending.actual_return_date.is_(None))
    result = await db.execute(stmt)
    lendings = result.scalars().all()

    return [
        {
            "lending_id": l.id,
            "book_copy_id": l.book_copy_id,
            "borrower_name": l.borrower_name,
            "borrower_contact": l.borrower_contact,
            "lent_date": l.lent_date.isoformat(),
            "expected_return_date": l.expected_return_date.isoformat() if l.expected_return_date else None,
            "is_overdue": l.is_overdue,
        }
        for l in lendings
    ]


async def mark_reminder_sent(db: AsyncSession, lending_id: int) -> None:
    """Mark a lending's reminder as sent."""
    stmt = select(Lending).where(Lending.id == lending_id)
    result = await db.execute(stmt)
    lending = result.scalar_one_or_none()
    if lending:
        lending.reminder_sent = True
        await db.flush()
