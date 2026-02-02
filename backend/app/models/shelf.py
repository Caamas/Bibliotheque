from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bookcase(Base):
    """A physical bookcase/furniture unit."""
    __tablename__ = "bookcases"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    room: Mapped[Optional[str]] = mapped_column(String(200))
    location_detail: Mapped[Optional[str]] = mapped_column(String(300))
    total_height_mm: Mapped[Optional[float]] = mapped_column(Float)
    total_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    total_depth_mm: Mapped[Optional[float]] = mapped_column(Float)
    adjustable_shelves: Mapped[bool] = mapped_column(default=True)
    photo: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    shelves: Mapped[list["Shelf"]] = relationship(
        back_populates="bookcase", cascade="all, delete-orphan",
        order_by="Shelf.shelf_number"
    )


class Shelf(Base):
    """A single shelf within a bookcase."""
    __tablename__ = "shelves"

    id: Mapped[int] = mapped_column(primary_key=True)
    bookcase_id: Mapped[int] = mapped_column(ForeignKey("bookcases.id"), index=True)
    shelf_number: Mapped[int] = mapped_column(Integer)  # 1 = top
    label: Mapped[Optional[str]] = mapped_column(String(100))
    usable_height_mm: Mapped[float] = mapped_column(Float)
    usable_width_mm: Mapped[float] = mapped_column(Float)
    usable_depth_mm: Mapped[Optional[float]] = mapped_column(Float)
    double_row: Mapped[bool] = mapped_column(Boolean, default=False)
    # If double_row, how much width is usable for the back row.
    # Typically same as usable_width_mm, but can differ if the shelf
    # is obstructed on one side.
    back_row_width_mm: Mapped[Optional[float]] = mapped_column(Float)
    photo: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bookcase: Mapped["Bookcase"] = relationship(back_populates="shelves")
    book_copies: Mapped[list["BookCopy"]] = relationship(
        back_populates="shelf", order_by="BookCopy.shelf_position"
    )


from app.models.book import BookCopy  # noqa: E402
