"""YoutubeAccount and Video models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class YoutubeAccount(Base):
    __tablename__ = "youtube_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    content_dna: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="youtube_accounts")
    videos = relationship("Video", back_populates="youtube_account", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<YoutubeAccount channel={self.channel_name}>"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    youtube_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("youtube_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=True)
    file_size_mb: Mapped[float] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("queued", "processing", "review", "done", "error", name="video_status"),
        default="queued",
        nullable=False,
    )
    checkpoint: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    copyright_status: Mapped[str] = mapped_column(
        Enum("unchecked", "clean", "flagged", name="copyright_status"),
        default="unchecked",
        nullable=False,
    )
    transcript: Mapped[str] = mapped_column(Text, nullable=True)
    transcript_segments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="videos")
    youtube_account = relationship("YoutubeAccount", back_populates="videos")
    clips = relationship("Clip", back_populates="video", lazy="dynamic")

    __table_args__ = (
        Index("ix_videos_user_status", "user_id", "status"),
        Index("ix_videos_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Video id={self.id} title={self.title!r} status={self.status}>"
