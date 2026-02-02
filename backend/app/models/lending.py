from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Date, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Lending(Base):
    """Tracks when a book copy is lent to someone."""
    __tablename__ = "lendings"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_copy_id: Mapped[int] = mapped_column(ForeignKey("book_copies.id"), index=True)
    borrower_name: Mapped[str] = mapped_column(String(200))
    borrower_contact: Mapped[Optional[str]] = mapped_column(String(300))
    lent_date: Mapped[date] = mapped_column(Date, default=date.today)
    expected_return_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_return_date: Mapped[Optional[date]] = mapped_column(Date)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    book_copy: Mapped["BookCopy"] = relationship(back_populates="lendings")

    @property
    def is_active(self) -> bool:
        return self.actual_return_date is None

    @property
    def is_overdue(self) -> bool:
        if not self.is_active or not self.expected_return_date:
            return False
        return date.today() > self.expected_return_date


from app.models.book import BookCopy  # noqa: E402
