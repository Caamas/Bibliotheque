"""Book and BookCopy CRUD endpoints."""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import settings
from app.models.book import Book, BookCopy, Award, BookAward, AwardStatus
from app.schemas.book import (
    BookCreate, BookUpdate, BookResponse, BookListResponse, BookDetailResponse,
    BookCopyCreate, BookCopyUpdate, BookCopyResponse,
    AwardCreate, AwardResponse, BookAwardCreate, BookAwardResponse,
)

router = APIRouter(prefix="/books", tags=["books"])


# --- Book CRUD ---

@router.get("", response_model=BookListResponse)
async def list_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    genre: Optional[str] = None,
    author: Optional[str] = None,
    publisher: Optional[str] = None,
    sort_by: str = Query("title", pattern="^(title|author|genre|publisher|created_at|last_read)$"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
):
    """List books with filtering, searching, and pagination."""
    stmt = select(Book)
    count_stmt = select(func.count(Book.id))

    # Filters
    if search:
        like_term = f"%{search}%"
        search_filter = or_(
            Book.title.ilike(like_term),
            Book.isbn_13.ilike(like_term),
            Book.isbn_10.ilike(like_term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    if genre:
        stmt = stmt.where(Book.genre.ilike(f"%{genre}%"))
        count_stmt = count_stmt.where(Book.genre.ilike(f"%{genre}%"))

    if publisher:
        stmt = stmt.where(Book.publisher.ilike(f"%{publisher}%"))
        count_stmt = count_stmt.where(Book.publisher.ilike(f"%{publisher}%"))

    # Get total count
    total = (await db.execute(count_stmt)).scalar() or 0

    # Sorting
    sort_col = getattr(Book, sort_by, Book.title)
    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # Pagination
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    stmt = stmt.options(selectinload(Book.copies))

    result = await db.execute(stmt)
    books = result.scalars().all()

    items = []
    for book in books:
        resp = BookResponse.model_validate(book)
        resp.copies_count = len(book.copies)
        items.append(resp)

    return BookListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """Get full book details including all copies."""
    stmt = (
        select(Book)
        .where(Book.id == book_id)
        .options(selectinload(Book.copies), selectinload(Book.awards))
    )
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    resp = BookDetailResponse.model_validate(book)
    resp.copies_count = len(book.copies)
    return resp


@router.post("", response_model=BookResponse, status_code=201)
async def create_book(data: BookCreate, db: AsyncSession = Depends(get_db)):
    """Create a new book entry."""
    # Check for duplicate ISBN
    if data.isbn_13:
        existing = await db.execute(select(Book).where(Book.isbn_13 == data.isbn_13))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Book with this ISBN-13 already exists")

    book = Book(**data.model_dump())
    db.add(book)
    await db.flush()
    await db.refresh(book)
    return BookResponse.model_validate(book)


@router.put("/{book_id}", response_model=BookResponse)
async def update_book(book_id: int, data: BookUpdate, db: AsyncSession = Depends(get_db)):
    """Update book metadata."""
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(book, key, value)

    await db.flush()
    await db.refresh(book)
    return BookResponse.model_validate(book)


@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a book and all its copies."""
    stmt = select(Book).where(Book.id == book_id)
    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    await db.delete(book)


@router.get("/check/{isbn}")
async def check_isbn(isbn: str, db: AsyncSession = Depends(get_db)):
    """Check if an ISBN is already in the collection."""
    isbn = isbn.replace("-", "").replace(" ", "").strip()
    stmt = select(Book).where(
        or_(Book.isbn_13 == isbn, Book.isbn_10 == isbn)
    ).options(selectinload(Book.copies))

    result = await db.execute(stmt)
    book = result.scalar_one_or_none()

    if book:
        return {
            "owned": True,
            "book_id": book.id,
            "title": book.title,
            "copies_count": len(book.copies),
            "personal_rating": book.copies[0].personal_rating if book.copies else None,
            "personal_review": book.copies[0].personal_review if book.copies else None,
        }
    return {"owned": False}


# --- BookCopy CRUD ---

@router.post("/copies", response_model=BookCopyResponse, status_code=201)
async def create_copy(data: BookCopyCreate, db: AsyncSession = Depends(get_db)):
    """Add a physical copy of a book."""
    # Verify book exists
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    copy = BookCopy(**data.model_dump())
    db.add(copy)
    await db.flush()
    await db.refresh(copy)
    return BookCopyResponse.model_validate(copy)


@router.put("/copies/{copy_id}", response_model=BookCopyResponse)
async def update_copy(copy_id: int, data: BookCopyUpdate, db: AsyncSession = Depends(get_db)):
    """Update a book copy (rating, review, shelf location, etc.)."""
    stmt = select(BookCopy).where(BookCopy.id == copy_id)
    result = await db.execute(stmt)
    copy = result.scalar_one_or_none()

    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(copy, key, value)

    await db.flush()
    await db.refresh(copy)
    return BookCopyResponse.model_validate(copy)


@router.post("/copies/{copy_id}/signature", response_model=BookCopyResponse)
async def upload_signature(
    copy_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a signature photo for a signed book."""
    stmt = select(BookCopy).where(BookCopy.id == copy_id)
    result = await db.execute(stmt)
    copy = result.scalar_one_or_none()

    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    # Save file
    filename = f"signature_{copy_id}_{file.filename}"
    filepath = settings.SIGNATURES_DIR / filename
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    copy.is_signed = True
    copy.signature_photo = str(filename)
    await db.flush()
    await db.refresh(copy)
    return BookCopyResponse.model_validate(copy)


# --- Awards ---

@router.get("/awards/list", response_model=list[AwardResponse])
async def list_awards(db: AsyncSession = Depends(get_db)):
    """List all known awards."""
    result = await db.execute(select(Award).order_by(Award.name))
    return [AwardResponse.model_validate(a) for a in result.scalars().all()]


@router.post("/awards", response_model=AwardResponse, status_code=201)
async def create_award(data: AwardCreate, db: AsyncSession = Depends(get_db)):
    """Create a new award."""
    award = Award(**data.model_dump())
    db.add(award)
    await db.flush()
    await db.refresh(award)
    return AwardResponse.model_validate(award)


@router.post("/{book_id}/awards", response_model=BookAwardResponse, status_code=201)
async def add_book_award(
    book_id: int, data: BookAwardCreate, db: AsyncSession = Depends(get_db)
):
    """Associate an award with a book."""
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    award = await db.get(Award, data.award_id)
    if not award:
        raise HTTPException(status_code=404, detail="Award not found")

    book_award = BookAward(
        book_id=book_id,
        award_id=data.award_id,
        year=data.year,
        status=AwardStatus(data.status),
    )
    db.add(book_award)
    await db.flush()
    await db.refresh(book_award, attribute_names=["award"])
    return BookAwardResponse.model_validate(book_award)
