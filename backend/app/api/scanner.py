"""ISBN scanning and lookup endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.book import Book, BookCopy
from app.schemas.book import (
    ISBNScanRequest, ISBNScanResponse, BookBase, BookResponse,
    BookCopyCreate, BookCopyResponse,
)
from app.services.isbn_lookup import lookup_isbn
from app.services.babelio import search_babelio

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.post("/scan", response_model=ISBNScanResponse)
async def scan_isbn(data: ISBNScanRequest, db: AsyncSession = Depends(get_db)):
    """Scan an ISBN: check if owned, otherwise fetch metadata.

    This is the primary endpoint for the scanning workflow:
    1. Normalize ISBN
    2. Check if already in collection
    3. If not, look up metadata from external APIs
    4. Return result for user confirmation
    """
    isbn = data.isbn.replace("-", "").replace(" ", "").strip()

    if not isbn or len(isbn) not in (10, 13):
        raise HTTPException(status_code=400, detail="Invalid ISBN format")

    # Check if already owned
    stmt = (
        select(Book)
        .where(or_(Book.isbn_13 == isbn, Book.isbn_10 == isbn))
        .options(selectinload(Book.copies))
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        resp = BookResponse.model_validate(existing)
        resp.copies_count = len(existing.copies)
        return ISBNScanResponse(
            found=True,
            already_owned=True,
            book=resp,
            message=f"You already own this book: {existing.title}",
        )

    # Look up metadata
    metadata = await lookup_isbn(isbn)

    if not metadata:
        return ISBNScanResponse(
            found=False,
            message=f"No metadata found for ISBN {isbn}. You can add the book manually.",
        )

    return ISBNScanResponse(
        found=True,
        already_owned=False,
        metadata=BookBase(
            isbn_13=metadata.isbn_13,
            isbn_10=metadata.isbn_10,
            title=metadata.title,
            subtitle=metadata.subtitle,
            authors=metadata.authors,
            publisher=metadata.publisher,
            publication_date=metadata.publication_date,
            page_count=metadata.page_count,
            height_mm=metadata.height_mm,
            width_mm=metadata.width_mm,
            depth_mm=metadata.depth_mm,
            cover_url=metadata.cover_url,
            genre=metadata.genre,
            language=metadata.language,
            description=metadata.description,
        ),
        message=f"Found: {metadata.title}",
    )


@router.post("/scan-and-add", response_model=BookResponse)
async def scan_and_add(data: ISBNScanRequest, db: AsyncSession = Depends(get_db)):
    """Scan ISBN and immediately add to collection (batch mode).

    For rapid scanning: looks up metadata and creates both the book
    and a default copy in one step.
    """
    isbn = data.isbn.replace("-", "").replace(" ", "").strip()

    # Check if already exists
    stmt = select(Book).where(or_(Book.isbn_13 == isbn, Book.isbn_10 == isbn))
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        return BookResponse.model_validate(existing)

    # Look up
    metadata = await lookup_isbn(isbn)
    if not metadata:
        raise HTTPException(status_code=404, detail=f"No metadata found for ISBN {isbn}")

    # Create book
    book = Book(
        isbn_13=metadata.isbn_13,
        isbn_10=metadata.isbn_10,
        title=metadata.title,
        subtitle=metadata.subtitle,
        authors=metadata.authors,
        publisher=metadata.publisher,
        publication_date=metadata.publication_date,
        page_count=metadata.page_count,
        height_mm=metadata.height_mm,
        width_mm=metadata.width_mm,
        depth_mm=metadata.depth_mm,
        cover_url=metadata.cover_url,
        genre=metadata.genre,
        language=metadata.language,
        description=metadata.description,
    )
    db.add(book)
    await db.flush()

    # Create default copy
    copy = BookCopy(book_id=book.id, condition="good")
    db.add(copy)
    await db.flush()
    await db.refresh(book)

    resp = BookResponse.model_validate(book)
    resp.copies_count = 1
    return resp


@router.post("/enrich/{book_id}")
async def enrich_from_babelio(book_id: int, db: AsyncSession = Depends(get_db)):
    """Enrich book data from Babelio (French book community)."""
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Search Babelio
    query = f"{book.title} {book.authors[0] if book.authors else ''}"
    babelio_info = await search_babelio(query, isbn=book.isbn_13)

    if not babelio_info:
        return {"enriched": False, "message": "Book not found on Babelio"}

    # Update book with Babelio data
    if babelio_info.url:
        book.babelio_url = babelio_info.url
    if babelio_info.rating:
        book.babelio_rating = babelio_info.rating
    if babelio_info.summary and not book.description:
        book.description = babelio_info.summary

    await db.flush()

    return {
        "enriched": True,
        "babelio_url": babelio_info.url,
        "babelio_rating": babelio_info.rating,
        "tags": babelio_info.tags,
    }
