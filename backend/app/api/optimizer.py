"""Shelf optimization endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.book import Book, BookCopy, StorageType
from app.models.shelf import Bookcase, Shelf
from app.schemas.shelf import (
    OptimizeRequest, OptimizeResponse, ShelfAssignmentResponse,
    ClusterInfo, ShelfUtilization,
    SuggestShelvesRequest, SuggestShelvesResponse, SuggestedShelf,
)
from app.services.shelf_optimizer import (
    BookForOptimizer, ShelfForOptimizer, SortOrder,
    optimize_shelves, suggest_shelf_configuration,
)

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.post("/optimize", response_model=OptimizeResponse)
async def run_optimization(
    data: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run shelf optimization for current book collection.

    Analyzes all books and shelves, then produces an optimal assignment
    that minimizes wasted vertical space and groups books by height.
    """
    # Fetch all book copies with their book metadata
    stmt = select(BookCopy).options(selectinload(BookCopy.book))

    if not data.include_long_term_storage:
        stmt = stmt.where(BookCopy.storage_type == StorageType.ACTIVE)

    result = await db.execute(stmt)
    copies = result.scalars().all()

    if not copies:
        raise HTTPException(status_code=400, detail="No books found to optimize")

    # Fetch shelves
    shelf_stmt = select(Shelf).options(selectinload(Shelf.bookcase))
    if data.bookcase_ids:
        shelf_stmt = shelf_stmt.where(Shelf.bookcase_id.in_(data.bookcase_ids))

    shelf_result = await db.execute(shelf_stmt)
    shelves = shelf_result.scalars().all()

    if not shelves:
        raise HTTPException(status_code=400, detail="No shelves configured")

    # Convert to optimizer format
    opt_books = [
        BookForOptimizer(
            copy_id=copy.id,
            book_id=copy.book_id,
            title=copy.book.title,
            authors=copy.book.authors or [],
            height_mm=copy.book.height_mm or 210,
            width_mm=copy.book.depth_mm or 25,  # depth_mm = spine width
            genre=copy.book.genre or "",
            publisher=copy.book.publisher or "",
            last_read=copy.last_read_date.isoformat() if copy.last_read_date else "",
        )
        for copy in copies
    ]

    opt_shelves = [
        ShelfForOptimizer(
            shelf_id=shelf.id,
            bookcase_id=shelf.bookcase_id,
            bookcase_name=shelf.bookcase.name if shelf.bookcase else "",
            shelf_number=shelf.shelf_number,
            usable_height_mm=shelf.usable_height_mm,
            usable_width_mm=shelf.usable_width_mm,
            adjustable=shelf.bookcase.adjustable_shelves if shelf.bookcase else True,
        )
        for shelf in shelves
    ]

    # Parse custom clusters
    custom_clusters = None
    if data.custom_clusters:
        custom_clusters = {
            name: (bounds[0], bounds[1])
            for name, bounds in data.custom_clusters.items()
        }

    # Run optimizer
    sort_order = SortOrder(data.sort_order)
    result = optimize_shelves(opt_books, opt_shelves, sort_order, custom_clusters)

    # Build response
    return OptimizeResponse(
        assignments=[
            ShelfAssignmentResponse(
                copy_id=a.copy_id,
                shelf_id=a.shelf_id,
                position=a.position,
                book_title=a.book_title,
            )
            for a in result.assignments
        ],
        unassigned_count=len(result.unassigned_books),
        clusters=[
            ClusterInfo(
                name=c.name,
                min_height=c.min_height,
                max_height=c.max_height,
                books_count=len(c.books),
                required_shelf_height=c.required_shelf_height,
                total_width_mm=c.total_width,
            )
            for c in result.clusters
        ],
        shelf_utilization=[
            ShelfUtilization(
                shelf_id=sid,
                **stats,
            )
            for sid, stats in result.shelf_utilization.items()
        ],
        suggested_shelf_heights=result.suggested_shelf_heights,
        total_books=result.total_books,
        assigned_count=result.assigned_count,
        warnings=result.warnings,
    )


@router.post("/apply")
async def apply_optimization(
    assignments: list[ShelfAssignmentResponse],
    db: AsyncSession = Depends(get_db),
):
    """Apply optimization results by updating book copy locations."""
    for assignment in assignments:
        copy = await db.get(BookCopy, assignment.copy_id)
        if copy:
            copy.shelf_id = assignment.shelf_id
            copy.shelf_position = assignment.position

    await db.flush()
    return {"applied": len(assignments)}


@router.post("/suggest-shelves", response_model=SuggestShelvesResponse)
async def suggest_shelf_config(
    data: SuggestShelvesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Suggest optimal shelf heights for an empty bookcase.

    Given bookcase dimensions and current book collection,
    calculates the ideal shelf positions.
    """
    # Get all active books
    stmt = select(BookCopy).options(selectinload(BookCopy.book)).where(
        BookCopy.storage_type == StorageType.ACTIVE,
        BookCopy.shelf_id.is_(None),  # Only unassigned books
    )
    result = await db.execute(stmt)
    copies = result.scalars().all()

    if not copies:
        raise HTTPException(status_code=400, detail="No unassigned books found")

    opt_books = [
        BookForOptimizer(
            copy_id=copy.id,
            book_id=copy.book_id,
            title=copy.book.title,
            authors=copy.book.authors or [],
            height_mm=copy.book.height_mm or 210,
            width_mm=copy.book.depth_mm or 25,
        )
        for copy in copies
    ]

    configs = suggest_shelf_configuration(
        opt_books,
        data.bookcase_height_mm,
        data.bookcase_width_mm,
        data.min_shelf_height_mm,
        data.shelf_thickness_mm,
    )

    total_used = sum(c["height_mm"] + data.shelf_thickness_mm for c in configs)

    return SuggestShelvesResponse(
        shelves=[SuggestedShelf(**c) for c in configs],
        total_shelves=len(configs),
        remaining_height_mm=round(data.bookcase_height_mm - total_used, 1),
    )
