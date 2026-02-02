"""Lending management endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.book import BookCopy
from app.models.lending import Lending
from app.schemas.lending import (
    LendingCreate, LendingReturn, LendingResponse, OverdueLendingResponse,
)
from app.services.reminder_service import get_overdue_lendings, get_active_lendings

router = APIRouter(prefix="/lendings", tags=["lendings"])


@router.get("", response_model=list[LendingResponse])
async def list_lendings(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List lendings, optionally filtered to active ones only."""
    stmt = select(Lending).order_by(Lending.lent_date.desc())
    if active_only:
        stmt = stmt.where(Lending.actual_return_date.is_(None))

    result = await db.execute(stmt)
    lendings = result.scalars().all()

    responses = []
    for lending in lendings:
        resp = LendingResponse.model_validate(lending)
        resp.is_active = lending.is_active
        resp.is_overdue = lending.is_overdue
        responses.append(resp)
    return responses


@router.get("/overdue", response_model=list[OverdueLendingResponse])
async def list_overdue(db: AsyncSession = Depends(get_db)):
    """List all overdue lendings."""
    overdue = await get_overdue_lendings(db)
    return overdue


@router.post("", response_model=LendingResponse, status_code=201)
async def create_lending(data: LendingCreate, db: AsyncSession = Depends(get_db)):
    """Record lending a book to someone."""
    # Verify copy exists
    copy = await db.get(BookCopy, data.book_copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Book copy not found")

    # Check if already lent out
    active_stmt = select(Lending).where(
        Lending.book_copy_id == data.book_copy_id,
        Lending.actual_return_date.is_(None),
    )
    existing = await db.execute(active_stmt)
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This copy is already lent out")

    lending = Lending(
        book_copy_id=data.book_copy_id,
        borrower_name=data.borrower_name,
        borrower_contact=data.borrower_contact,
        lent_date=data.lent_date or date.today(),
        expected_return_date=data.expected_return_date,
        notes=data.notes,
    )
    db.add(lending)
    await db.flush()
    await db.refresh(lending)

    resp = LendingResponse.model_validate(lending)
    resp.is_active = True
    resp.is_overdue = False
    return resp


@router.put("/{lending_id}/return", response_model=LendingResponse)
async def return_book(
    lending_id: int, data: LendingReturn, db: AsyncSession = Depends(get_db)
):
    """Record that a lent book has been returned."""
    stmt = select(Lending).where(Lending.id == lending_id)
    result = await db.execute(stmt)
    lending = result.scalar_one_or_none()

    if not lending:
        raise HTTPException(status_code=404, detail="Lending not found")

    if lending.actual_return_date:
        raise HTTPException(status_code=409, detail="Book already returned")

    lending.actual_return_date = data.actual_return_date or date.today()
    await db.flush()
    await db.refresh(lending)

    resp = LendingResponse.model_validate(lending)
    resp.is_active = False
    resp.is_overdue = False
    return resp


@router.delete("/{lending_id}", status_code=204)
async def delete_lending(lending_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a lending record."""
    stmt = select(Lending).where(Lending.id == lending_id)
    result = await db.execute(stmt)
    lending = result.scalar_one_or_none()

    if not lending:
        raise HTTPException(status_code=404, detail="Lending not found")

    await db.delete(lending)
