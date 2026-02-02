from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Book (abstract work) ---

class BookBase(BaseModel):
    isbn_13: Optional[str] = None
    isbn_10: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    page_count: Optional[int] = None
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    cover_url: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    babelio_url: Optional[str] = None
    babelio_rating: Optional[float] = None


class BookCreate(BookBase):
    pass


class BookUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    authors: Optional[list[str]] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    page_count: Optional[int] = None
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    cover_url: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    babelio_url: Optional[str] = None
    babelio_rating: Optional[float] = None


class BookResponse(BookBase):
    id: int
    cover_local: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    copies_count: int = 0

    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    items: list[BookResponse]
    total: int
    page: int
    page_size: int


# --- BookCopy (physical copy) ---

class BookCopyBase(BaseModel):
    condition: Optional[str] = None
    is_signed: bool = False
    purchase_date: Optional[date] = None
    purchase_location: Optional[str] = None
    purchase_price: Optional[float] = None
    personal_rating: Optional[float] = Field(None, ge=0, le=5)
    personal_review: Optional[str] = None
    last_read_date: Optional[date] = None
    read_count: int = 0
    storage_type: str = "active"


class BookCopyCreate(BookCopyBase):
    book_id: int


class BookCopyUpdate(BaseModel):
    condition: Optional[str] = None
    is_signed: Optional[bool] = None
    purchase_date: Optional[date] = None
    purchase_location: Optional[str] = None
    purchase_price: Optional[float] = None
    personal_rating: Optional[float] = Field(None, ge=0, le=5)
    personal_review: Optional[str] = None
    last_read_date: Optional[date] = None
    read_count: Optional[int] = None
    storage_type: Optional[str] = None
    shelf_id: Optional[int] = None
    shelf_position: Optional[int] = None


class BookCopyResponse(BookCopyBase):
    id: int
    book_id: int
    signature_photo: Optional[str] = None
    shelf_id: Optional[int] = None
    shelf_position: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookDetailResponse(BookResponse):
    """Full book detail including copies."""
    copies: list[BookCopyResponse] = []


# --- ISBN Scan ---

class ISBNScanRequest(BaseModel):
    isbn: str


class ISBNScanResponse(BaseModel):
    found: bool
    already_owned: bool = False
    book: Optional[BookResponse] = None
    metadata: Optional[BookBase] = None
    message: str = ""


# --- Award ---

class AwardCreate(BaseModel):
    name: str
    country: Optional[str] = None


class AwardResponse(BaseModel):
    id: int
    name: str
    country: Optional[str] = None

    class Config:
        from_attributes = True


class BookAwardCreate(BaseModel):
    award_id: int
    year: Optional[int] = None
    status: str = "nominated"  # nominated, shortlisted, won


class BookAwardResponse(BaseModel):
    id: int
    book_id: int
    award_id: int
    year: Optional[int] = None
    status: str
    award: AwardResponse

    class Config:
        from_attributes = True
