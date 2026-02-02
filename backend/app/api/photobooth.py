"""Photobooth API: process book photos for metadata extraction."""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.photobooth import process_book, PhotoboothResult
from app.services.enrichment import (
    run_batch_enrichment, apply_enrichment,
    get_enrichment_stats, find_books_needing_enrichment,
    enrich_single_book,
)
from app.services.isbn_lookup import ISBNLookupService

SIGNATURES_DIR = Path(settings.UPLOAD_DIR) / "signatures"

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/photobooth", tags=["photobooth"])


class PhotoboothResponse(BaseModel):
    """Response from photobooth processing."""
    isbn: Optional[str] = None
    title: Optional[str] = None
    authors: list[str] = []
    publisher: Optional[str] = None
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    isbn_confidence: float = 0.0
    title_confidence: float = 0.0
    dimension_confidence: float = 0.0
    warnings: list[str] = []
    # OCR raw text for debugging
    front_raw_text: Optional[str] = None
    back_raw_text: Optional[str] = None
    spine_raw_text: Optional[str] = None
    # API-enriched data (if ISBN was found)
    api_title: Optional[str] = None
    api_authors: list[str] = []
    api_publisher: Optional[str] = None
    api_description: Optional[str] = None
    api_cover_url: Optional[str] = None
    api_page_count: Optional[int] = None
    api_height_mm: Optional[float] = None
    # Signature photo (if provided)
    is_signed: bool = False
    signature_photo_path: Optional[str] = None


@router.post("/process", response_model=PhotoboothResponse)
async def process_photos(
    front: Optional[UploadFile] = File(None),
    back: Optional[UploadFile] = File(None),
    spine: Optional[UploadFile] = File(None),
    signature: Optional[UploadFile] = File(None),
):
    """Process book photos taken on the calibration mat.

    Upload 1-4 photos:
    - front: front cover (for title, author, dimensions)
    - back: back cover (for ISBN barcode)
    - spine: spine (for depth measurement, title confirmation)
    - signature: photo of author's signature (optional, stored as-is)

    Returns extracted metadata with confidence scores.
    The client should present this for user confirmation before saving.
    """
    if not any([front, back, spine]):
        raise HTTPException(status_code=400, detail="At least one photo is required")

    # Read uploaded files
    front_data = await front.read() if front else None
    back_data = await back.read() if back else None
    spine_data = await spine.read() if spine else None

    # Save signature photo if provided
    signature_path = None
    if signature:
        SIGNATURES_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(signature.filename or "sig.jpg").suffix or ".jpg"
        sig_filename = f"{uuid.uuid4().hex}{ext}"
        sig_path = SIGNATURES_DIR / sig_filename
        sig_data = await signature.read()
        sig_path.write_bytes(sig_data)
        signature_path = f"signatures/{sig_filename}"

    # Process through the photobooth pipeline
    result = process_book(front_data, back_data, spine_data)

    # Build response
    response = PhotoboothResponse(
        isbn=result.isbn,
        title=result.title,
        authors=result.authors,
        publisher=result.publisher,
        height_mm=result.height_mm,
        width_mm=result.width_mm,
        depth_mm=result.depth_mm,
        isbn_confidence=result.isbn_confidence,
        title_confidence=result.title_confidence,
        dimension_confidence=result.dimension_confidence,
        warnings=result.warnings,
        front_raw_text=result.front_ocr.raw_text if result.front_ocr else None,
        back_raw_text=result.back_ocr.raw_text if result.back_ocr else None,
        spine_raw_text=result.spine_ocr.raw_text if result.spine_ocr else None,
        is_signed=signature_path is not None,
        signature_photo_path=signature_path,
    )

    # If we got an ISBN, try to enrich from APIs
    if result.isbn:
        try:
            lookup = ISBNLookupService()
            api_data = await lookup.lookup(result.isbn)
            if api_data:
                response.api_title = api_data.title
                response.api_authors = api_data.authors or []
                response.api_publisher = api_data.publisher
                response.api_description = api_data.description
                response.api_cover_url = api_data.cover_url
                response.api_page_count = api_data.page_count
                response.api_height_mm = api_data.height_mm
        except Exception as e:
            logger.warning("API enrichment failed for ISBN %s: %s", result.isbn, e)
            response.warnings.append(f"API lookup failed: {e}")

    return response


# --- Batch Enrichment Endpoints ---

# In-memory enrichment job state (simple approach for single-server)
_enrichment_job = {"running": False, "progress": 0, "total": 0, "result": None}


def _progress_callback(current: int, total: int):
    _enrichment_job["progress"] = current
    _enrichment_job["total"] = total


class EnrichmentStatsResponse(BaseModel):
    total_books: int
    with_isbn: int
    with_height: int
    with_description: int
    with_cover: int
    completeness_pct: float


class EnrichmentProposal(BaseModel):
    book_id: int
    isbn: str
    title: str
    proposals: dict


class BatchEnrichmentResponse(BaseModel):
    total: int
    enriched: int
    failed: int
    skipped: int
    proposals: list[EnrichmentProposal]


class ApplyEnrichmentRequest(BaseModel):
    book_id: int
    accepted_fields: dict


@router.get("/enrichment/stats", response_model=EnrichmentStatsResponse)
async def enrichment_stats(db: AsyncSession = Depends(get_db)):
    """Get statistics about metadata completeness of the collection."""
    stats = await get_enrichment_stats(db)
    return EnrichmentStatsResponse(**stats)


@router.post("/enrichment/start")
async def start_batch_enrichment(background_tasks: BackgroundTasks):
    """Start a batch enrichment job in the background.

    Queries Open Library and Google Books for all books with ISBN
    that have incomplete metadata. Results are stored for user validation.
    """
    if _enrichment_job["running"]:
        raise HTTPException(status_code=409, detail="Enrichment job already running")

    async def _run():
        _enrichment_job["running"] = True
        try:
            result = await run_batch_enrichment(
                batch_size=20,
                delay_seconds=1.5,  # rate limit: ~40 req/min
                on_progress=_progress_callback,
            )
            _enrichment_job["result"] = result
        finally:
            _enrichment_job["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Enrichment job started in background"}


@router.get("/enrichment/status")
async def enrichment_status():
    """Check the status of the running enrichment job."""
    return {
        "running": _enrichment_job["running"],
        "progress": _enrichment_job["progress"],
        "total": _enrichment_job["total"],
        "has_results": _enrichment_job["result"] is not None,
    }


@router.get("/enrichment/results", response_model=BatchEnrichmentResponse)
async def enrichment_results():
    """Get the results of the last batch enrichment job."""
    if _enrichment_job["result"] is None:
        raise HTTPException(status_code=404, detail="No enrichment results available. Start a job first.")

    data = _enrichment_job["result"]
    return BatchEnrichmentResponse(
        total=data["total"],
        enriched=data["enriched"],
        failed=data["failed"],
        skipped=data["skipped"],
        proposals=[EnrichmentProposal(**p) for p in data["proposals"]],
    )


@router.post("/enrichment/apply")
async def apply_enrichment_endpoint(
    req: ApplyEnrichmentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Apply user-validated enrichment to a specific book.

    Send the book_id and a dict of accepted field values.
    """
    book = await apply_enrichment(db, req.book_id, req.accepted_fields)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"status": "applied", "book_id": book.id}


@router.post("/enrichment/apply-all")
async def apply_all_enrichment(
    proposals: list[ApplyEnrichmentRequest],
    db: AsyncSession = Depends(get_db),
):
    """Apply enrichment for multiple books at once (bulk accept)."""
    applied = 0
    for req in proposals:
        book = await apply_enrichment(db, req.book_id, req.accepted_fields)
        if book:
            applied += 1
    return {"status": "applied", "count": applied}
