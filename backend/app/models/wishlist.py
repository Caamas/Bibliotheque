import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Wishlist(Base):
    """A named wishlist that can be shared."""
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    share_token: Mapped[str] = mapped_column(
        String(64), unique=True, default=lambda: secrets.token_urlsafe(32)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="wishlist", cascade="all, delete-orphan",
        order_by="WishlistItem.priority.desc()"
    )


class WishlistItem(Base):
    """An item in a wishlist - may reference an existing book or just ISBN/title."""
    __tablename__ = "wishlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    wishlist_id: Mapped[int] = mapped_column(ForeignKey("wishlists.id"), index=True)
    book_id: Mapped[Optional[int]] = mapped_column(ForeignKey("books.id"))
    isbn: Mapped[Optional[str]] = mapped_column(String(13))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    author: Mapped[Optional[str]] = mapped_column(String(300))
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = more wanted
    notes: Mapped[Optional[str]] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    wishlist: Mapped["Wishlist"] = relationship(back_populates="items")
