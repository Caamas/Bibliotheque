from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WishlistBase(BaseModel):
    name: str


class WishlistCreate(WishlistBase):
    pass


class WishlistResponse(WishlistBase):
    id: int
    share_token: str
    items_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class WishlistItemBase(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    priority: int = 0
    notes: Optional[str] = None


class WishlistItemCreate(WishlistItemBase):
    book_id: Optional[int] = None


class WishlistItemResponse(WishlistItemBase):
    id: int
    wishlist_id: int
    book_id: Optional[int] = None
    added_at: datetime

    class Config:
        from_attributes = True


class WishlistDetailResponse(WishlistResponse):
    items: list[WishlistItemResponse] = []


class WishlistShareResponse(BaseModel):
    """Public view of a shared wishlist."""
    name: str
    items: list[WishlistItemResponse]
