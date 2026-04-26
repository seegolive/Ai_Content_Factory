"""Clip model."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=True)
    viral_score: Mapped[int] = mapped_column(Integer, nullable=True)
    hook_text: Mapped[str] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=True)
    clip_path: Mapped[str] = mapped_column(Text, nullable=True)
    format: Mapped[str] = mapped_column(
        Enum("horizontal", "vertical", "square", name="clip_format"),
        default="vertical",
        nullable=False,
    )
    qc_status: Mapped[str] = mapped_column(
        Enum("pending", "passed", "failed", "manual_review", name="qc_status"),
        default="pending",
        nullable=False,
    )
    qc_issues: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    review_status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", name="review_status"),
        default="pending",
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    platform_status: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    speaker_id: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    video = relationship("Video", back_populates="clips")

    __table_args__ = (
        Index("ix_clips_video_review", "video_id", "review_status"),
        Index("ix_clips_viral_score", "viral_score"),
    )

    def __repr__(self) -> str:
        return f"<Clip id={self.id} score={self.viral_score} review={self.review_status}>"
