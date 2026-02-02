import enum
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String, Integer, Float, Text, Boolean, Date, DateTime,
    Enum, JSON, ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StorageType(str, enum.Enum):
    ACTIVE = "active"
    LONG_TERM = "long_term"


class AwardStatus(str, enum.Enum):
    NOMINATED = "nominated"
    SHORTLISTED = "shortlisted"
    WON = "won"


class Book(Base):
    """A book as an abstract work (identified by ISBN/title+author)."""
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn_13: Mapped[Optional[str]] = mapped_column(String(13), index=True, unique=True)
    isbn_10: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(500))
    authors: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    publisher: Mapped[Optional[str]] = mapped_column(String(300))
    publication_date: Mapped[Optional[str]] = mapped_column(String(20))
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    height_mm: Mapped[Optional[float]] = mapped_column(Float)
    width_mm: Mapped[Optional[float]] = mapped_column(Float)
    depth_mm: Mapped[Optional[float]] = mapped_column(Float)
    cover_url: Mapped[Optional[str]] = mapped_column(String(1000))
    cover_local: Mapped[Optional[str]] = mapped_column(String(500))
    genre: Mapped[Optional[str]] = mapped_column(String(200), index=True)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    description: Mapped[Optional[str]] = mapped_column(Text)
    babelio_url: Mapped[Optional[str]] = mapped_column(String(500))
    babelio_rating: Mapped[Optional[float]] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    copies: Mapped[list["BookCopy"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    awards: Mapped[list["BookAward"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class BookCopy(Base):
    """A physical copy of a book that you own."""
    __tablename__ = "book_copies"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    condition: Mapped[Optional[str]] = mapped_column(String(50))  # new, good, fair, poor
    is_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_photo: Mapped[Optional[str]] = mapped_column(String(500))
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)
    purchase_location: Mapped[Optional[str]] = mapped_column(String(300))
    purchase_price: Mapped[Optional[float]] = mapped_column(Float)
    personal_rating: Mapped[Optional[float]] = mapped_column(Float)  # 0-5, half stars
    personal_review: Mapped[Optional[str]] = mapped_column(Text)
    last_read_date: Mapped[Optional[date]] = mapped_column(Date)
    read_count: Mapped[int] = mapped_column(Integer, default=0)
    storage_type: Mapped[StorageType] = mapped_column(
        Enum(StorageType), default=StorageType.ACTIVE
    )
    shelf_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shelves.id"))
    shelf_position: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    book: Mapped["Book"] = relationship(back_populates="copies")
    shelf: Mapped[Optional["Shelf"]] = relationship(back_populates="book_copies")
    lendings: Mapped[list["Lending"]] = relationship(back_populates="book_copy", cascade="all, delete-orphan")


class Award(Base):
    """A literary award (e.g. Prix Goncourt, Booker Prize)."""
    __tablename__ = "awards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True)
    country: Mapped[Optional[str]] = mapped_column(String(100))


class BookAward(Base):
    """Association between a book and an award."""
    __tablename__ = "book_awards"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), index=True)
    award_id: Mapped[int] = mapped_column(ForeignKey("awards.id"), index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[AwardStatus] = mapped_column(Enum(AwardStatus))

    book: Mapped["Book"] = relationship(back_populates="awards")
    award: Mapped["Award"] = relationship()


# Avoid circular import - Shelf and Lending are imported via relationship strings
from app.models.shelf import Shelf  # noqa: E402
from app.models.lending import Lending  # noqa: E402
