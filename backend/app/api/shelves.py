"""Bookcase and Shelf management endpoints."""

import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.shelf import Bookcase, Shelf
from app.schemas.shelf import (
    BookcaseCreate, BookcaseUpdate, BookcaseResponse, BookcaseDetailResponse,
    ShelfCreate, ShelfUpdate, ShelfResponse,
)

router = APIRouter(prefix="/shelves", tags=["shelves"])


# --- Bookcase CRUD ---

@router.get("/bookcases", response_model=list[BookcaseResponse])
async def list_bookcases(db: AsyncSession = Depends(get_db)):
    """List all bookcases."""
    result = await db.execute(select(Bookcase).order_by(Bookcase.name))
    return [BookcaseResponse.model_validate(bc) for bc in result.scalars().all()]


@router.get("/bookcases/{bookcase_id}", response_model=BookcaseDetailResponse)
async def get_bookcase(bookcase_id: int, db: AsyncSession = Depends(get_db)):
    """Get bookcase details including all shelves."""
    stmt = (
        select(Bookcase)
        .where(Bookcase.id == bookcase_id)
        .options(selectinload(Bookcase.shelves).selectinload(Shelf.book_copies))
    )
    result = await db.execute(stmt)
    bc = result.scalar_one_or_none()

    if not bc:
        raise HTTPException(status_code=404, detail="Bookcase not found")

    resp = BookcaseDetailResponse.model_validate(bc)
    for i, shelf in enumerate(bc.shelves):
        resp.shelves[i].books_count = len(shelf.book_copies)
    return resp


@router.post("/bookcases", response_model=BookcaseResponse, status_code=201)
async def create_bookcase(data: BookcaseCreate, db: AsyncSession = Depends(get_db)):
    """Create a new bookcase."""
    bc = Bookcase(**data.model_dump())
    db.add(bc)
    await db.flush()
    await db.refresh(bc)
    return BookcaseResponse.model_validate(bc)


@router.put("/bookcases/{bookcase_id}", response_model=BookcaseResponse)
async def update_bookcase(
    bookcase_id: int, data: BookcaseUpdate, db: AsyncSession = Depends(get_db)
):
    """Update bookcase details."""
    bc = await db.get(Bookcase, bookcase_id)
    if not bc:
        raise HTTPException(status_code=404, detail="Bookcase not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(bc, key, value)

    await db.flush()
    await db.refresh(bc)
    return BookcaseResponse.model_validate(bc)


@router.delete("/bookcases/{bookcase_id}", status_code=204)
async def delete_bookcase(bookcase_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a bookcase and all its shelves."""
    bc = await db.get(Bookcase, bookcase_id)
    if not bc:
        raise HTTPException(status_code=404, detail="Bookcase not found")
    await db.delete(bc)


@router.post("/bookcases/{bookcase_id}/photo", response_model=BookcaseResponse)
async def upload_bookcase_photo(
    bookcase_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a photo of the bookcase."""
    bc = await db.get(Bookcase, bookcase_id)
    if not bc:
        raise HTTPException(status_code=404, detail="Bookcase not found")

    filename = f"bookcase_{bookcase_id}_{file.filename}"
    filepath = settings.SHELVES_DIR / filename
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    bc.photo = str(filename)
    await db.flush()
    await db.refresh(bc)
    return BookcaseResponse.model_validate(bc)


# --- Shelf CRUD ---

@router.post("", response_model=ShelfResponse, status_code=201)
async def create_shelf(data: ShelfCreate, db: AsyncSession = Depends(get_db)):
    """Create a new shelf in a bookcase."""
    bc = await db.get(Bookcase, data.bookcase_id)
    if not bc:
        raise HTTPException(status_code=404, detail="Bookcase not found")

    shelf = Shelf(**data.model_dump())
    db.add(shelf)
    await db.flush()
    await db.refresh(shelf)
    return ShelfResponse.model_validate(shelf)


@router.put("/{shelf_id}", response_model=ShelfResponse)
async def update_shelf(shelf_id: int, data: ShelfUpdate, db: AsyncSession = Depends(get_db)):
    """Update shelf dimensions or label."""
    shelf = await db.get(Shelf, shelf_id)
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(shelf, key, value)

    await db.flush()
    await db.refresh(shelf)
    return ShelfResponse.model_validate(shelf)


@router.delete("/{shelf_id}", status_code=204)
async def delete_shelf(shelf_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a shelf."""
    shelf = await db.get(Shelf, shelf_id)
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")
    await db.delete(shelf)


@router.post("/{shelf_id}/photo", response_model=ShelfResponse)
async def upload_shelf_photo(
    shelf_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a photo of a shelf."""
    shelf = await db.get(Shelf, shelf_id)
    if not shelf:
        raise HTTPException(status_code=404, detail="Shelf not found")

    filename = f"shelf_{shelf_id}_{file.filename}"
    filepath = settings.SHELVES_DIR / filename
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    shelf.photo = str(filename)
    await db.flush()
    await db.refresh(shelf)
    return ShelfResponse.model_validate(shelf)
