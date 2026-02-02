"""Batch enrichment service: queries internet APIs for book metadata.

Processes books that have an ISBN but incomplete metadata.
Runs as a background task, populating a validation queue for user review.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.book import Book
from app.services.isbn_lookup import ISBNLookupService

logger = logging.getLogger(__name__)


class EnrichmentStatus(str, Enum):
    PENDING = "pending"
    ENRICHED = "enriched"        # API data fetched, awaiting validation
    VALIDATED = "validated"       # User accepted the enrichment
    REJECTED = "rejected"         # User rejected (keeps original data)
    FAILED = "failed"             # API lookup failed
    NO_ISBN = "no_isbn"           # No ISBN to look up


class EnrichmentField(str, Enum):
    """Fields that can be enriched from APIs."""
    TITLE = "title"
    AUTHORS = "authors"
    PUBLISHER = "publisher"
    PUBLICATION_DATE = "publication_date"
    PAGE_COUNT = "page_count"
    HEIGHT_MM = "height_mm"
    WIDTH_MM = "width_mm"
    DEPTH_MM = "depth_mm"
    DESCRIPTION = "description"
    COVER_URL = "cover_url"
    GENRE = "genre"
    LANGUAGE = "language"


async def find_books_needing_enrichment(db: AsyncSession) -> list[Book]:
    """Find books with ISBN that have incomplete metadata."""
    stmt = select(Book).where(
        Book.isbn.isnot(None),
        Book.isbn != "",
        or_(
            Book.title.is_(None),
            Book.title == "",
            Book.authors.is_(None),
            Book.publisher.is_(None),
            Book.height_mm.is_(None),
            Book.description.is_(None),
            Book.page_count.is_(None),
        ),
    ).order_by(Book.created_at.desc())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def enrich_single_book(
    isbn: str, current_data: dict | None = None
) -> dict:
    """Fetch metadata for a single ISBN and return proposed changes.

    Returns a dict of {field_name: {current: ..., proposed: ..., source: ...}}
    Only includes fields where the proposed value differs from current.
    """
    lookup = ISBNLookupService()
    api_data = await lookup.lookup(isbn)

    if api_data is None:
        return {}

    current = current_data or {}
    proposals = {}

    field_mapping = {
        "title": "title",
        "authors": "authors",
        "publisher": "publisher",
        "publication_date": "publication_date",
        "page_count": "page_count",
        "height_mm": "height_mm",
        "width_mm": "width_mm",
        "depth_mm": "depth_mm",
        "description": "description",
        "cover_url": "cover_url",
        "genre": "genre",
        "language": "language",
    }

    for api_field, db_field in field_mapping.items():
        proposed = getattr(api_data, api_field, None)
        if proposed is None:
            continue

        current_val = current.get(db_field)

        # Only propose if current is empty/None or proposed is different
        if current_val is None or current_val == "" or current_val == []:
            proposals[db_field] = {
                "current": current_val,
                "proposed": proposed,
                "source": api_data.source if hasattr(api_data, "source") else "api",
            }

    return proposals


async def run_batch_enrichment(
    batch_size: int = 20,
    delay_seconds: float = 1.0,
    on_progress: callable = None,
) -> dict:
    """Run batch enrichment for all books needing it.

    Processes books in batches with rate limiting.
    Returns summary statistics.
    """
    stats = {
        "total": 0,
        "enriched": 0,
        "failed": 0,
        "skipped": 0,
        "proposals": [],  # list of {book_id, isbn, proposals}
    }

    async with async_session() as db:
        books = await find_books_needing_enrichment(db)
        stats["total"] = len(books)

        logger.info("Starting batch enrichment for %d books", len(books))

        for i, book in enumerate(books):
            if not book.isbn:
                stats["skipped"] += 1
                continue

            try:
                current_data = {
                    "title": book.title,
                    "authors": book.authors,
                    "publisher": book.publisher,
                    "publication_date": book.publication_date,
                    "page_count": book.page_count,
                    "height_mm": book.height_mm,
                    "width_mm": book.width_mm,
                    "depth_mm": book.depth_mm,
                    "description": book.description,
                    "cover_url": book.cover_url,
                    "genre": book.genre,
                    "language": book.language,
                }

                proposals = await enrich_single_book(book.isbn, current_data)

                if proposals:
                    stats["enriched"] += 1
                    stats["proposals"].append({
                        "book_id": book.id,
                        "isbn": book.isbn,
                        "title": book.title or f"[ISBN: {book.isbn}]",
                        "proposals": proposals,
                    })
                else:
                    stats["skipped"] += 1

            except Exception as e:
                logger.error("Enrichment failed for ISBN %s: %s", book.isbn, e)
                stats["failed"] += 1

            # Rate limiting
            if i < len(books) - 1:
                await asyncio.sleep(delay_seconds)

            # Progress callback
            if on_progress:
                on_progress(i + 1, len(books))

        logger.info(
            "Batch enrichment complete: %d enriched, %d failed, %d skipped out of %d",
            stats["enriched"], stats["failed"], stats["skipped"], stats["total"],
        )

    return stats


async def apply_enrichment(
    db: AsyncSession,
    book_id: int,
    accepted_fields: dict[str, any],
) -> Book | None:
    """Apply user-validated enrichment to a book.

    accepted_fields is a dict of {field_name: value} for fields the user accepted.
    """
    book = await db.get(Book, book_id)
    if book is None:
        return None

    for field_name, value in accepted_fields.items():
        if hasattr(book, field_name):
            setattr(book, field_name, value)

    book.updated_at = datetime.utcnow()
    await db.flush()
    return book


async def get_enrichment_stats(db: AsyncSession) -> dict:
    """Get statistics about enrichment state of the collection."""
    total = await db.scalar(select(func.count(Book.id)))
    with_isbn = await db.scalar(select(func.count(Book.id)).where(Book.isbn.isnot(None)))
    with_height = await db.scalar(select(func.count(Book.id)).where(Book.height_mm.isnot(None)))
    with_description = await db.scalar(select(func.count(Book.id)).where(Book.description.isnot(None)))
    with_cover = await db.scalar(select(func.count(Book.id)).where(Book.cover_url.isnot(None)))

    return {
        "total_books": total or 0,
        "with_isbn": with_isbn or 0,
        "with_height": with_height or 0,
        "with_description": with_description or 0,
        "with_cover": with_cover or 0,
        "completeness_pct": round(
            ((with_height or 0) + (with_description or 0) + (with_cover or 0))
            / max((total or 1) * 3, 1) * 100, 1
        ),
    }
