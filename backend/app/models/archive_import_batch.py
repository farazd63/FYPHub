"""Import history for administrator archive workbook uploads."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ArchiveImportBatch(Base):
    __tablename__ = "archive_import_batches"

    batch_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    inserted_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    import_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="PROCESSING")
