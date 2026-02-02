from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Bookcase ---

class BookcaseBase(BaseModel):
    name: str
    room: Optional[str] = None
    location_detail: Optional[str] = None
    total_height_mm: Optional[float] = None
    total_width_mm: Optional[float] = None
    total_depth_mm: Optional[float] = None
    adjustable_shelves: bool = True


class BookcaseCreate(BookcaseBase):
    pass


class BookcaseUpdate(BaseModel):
    name: Optional[str] = None
    room: Optional[str] = None
    location_detail: Optional[str] = None
    total_height_mm: Optional[float] = None
    total_width_mm: Optional[float] = None
    total_depth_mm: Optional[float] = None
    adjustable_shelves: Optional[bool] = None


class BookcaseResponse(BookcaseBase):
    id: int
    photo: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Shelf ---

class ShelfBase(BaseModel):
    shelf_number: int
    label: Optional[str] = None
    usable_height_mm: float
    usable_width_mm: float
    usable_depth_mm: Optional[float] = None
    double_row: bool = False  # Whether this shelf supports two rows of books
    back_row_width_mm: Optional[float] = None  # Usable width for back row


class ShelfCreate(ShelfBase):
    bookcase_id: int


class ShelfUpdate(BaseModel):
    shelf_number: Optional[int] = None
    label: Optional[str] = None
    usable_height_mm: Optional[float] = None
    usable_width_mm: Optional[float] = None
    usable_depth_mm: Optional[float] = None
    double_row: Optional[bool] = None
    back_row_width_mm: Optional[float] = None


class ShelfResponse(ShelfBase):
    id: int
    bookcase_id: int
    photo: Optional[str] = None
    books_count: int = 0
    front_row_books: int = 0
    back_row_books: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class BookcaseDetailResponse(BookcaseResponse):
    shelves: list[ShelfResponse] = []


# --- Optimizer ---

class OptimizeRequest(BaseModel):
    """Request to run shelf optimizer."""
    sort_order: str = "author"  # author, genre, publisher, title, last_read
    include_long_term_storage: bool = False
    bookcase_ids: Optional[list[int]] = None  # None = all bookcases
    custom_clusters: Optional[dict[str, list[float]]] = None  # name -> [min_h, max_h]


class ShelfAssignmentResponse(BaseModel):
    copy_id: int
    shelf_id: int
    position: int
    book_title: str
    layer: str = "front"  # "front" or "back"


class ClusterInfo(BaseModel):
    name: str
    min_height: float
    max_height: float
    books_count: int
    required_shelf_height: float
    total_width_mm: float


class ShelfUtilization(BaseModel):
    shelf_id: int
    books_count: int
    front_row_books: int = 0
    back_row_books: int = 0
    width_used_mm: float
    width_total_mm: float
    width_utilization_pct: float
    max_book_height_mm: float
    height_available_mm: float
    height_wasted_mm: float


class OptimizeResponse(BaseModel):
    assignments: list[ShelfAssignmentResponse]
    unassigned_count: int
    clusters: list[ClusterInfo]
    shelf_utilization: list[ShelfUtilization]
    suggested_shelf_heights: dict[int, float]
    total_books: int
    assigned_count: int
    warnings: list[str]


class SuggestShelvesRequest(BaseModel):
    """Request to suggest shelf configuration for an empty bookcase."""
    bookcase_height_mm: float
    bookcase_width_mm: float
    min_shelf_height_mm: float = 160
    shelf_thickness_mm: float = 20


class SuggestedShelf(BaseModel):
    cluster: str
    height_mm: float
    books_count: int
    max_book_height_mm: float


class SuggestShelvesResponse(BaseModel):
    shelves: list[SuggestedShelf]
    total_shelves: int
    remaining_height_mm: float
