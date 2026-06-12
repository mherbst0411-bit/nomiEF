"""Database layer.

SQLAlchemy models + session factory. Defaults to SQLite for friction-free
local dev and demos; set NOMI_DATABASE_URL to a Postgres DSN in staging or
production (docker-compose ships Postgres).

Privacy notes (see docs/LEGAL_COMPLIANCE.md):
  * TasteProfileRow.data is personal data — covered by the deletion
    endpoint (DELETE /v1/users/{id}) which cascades to all rows + audio.
  * We store behavioral events, not raw listening audio, for Pillar 1.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer,
                        String, Text, create_engine)
from sqlalchemy.orm import (DeclarativeBase, Mapped, mapped_column,
                            relationship, sessionmaker)

DATABASE_URL = os.environ.get("NOMI_DATABASE_URL", "sqlite:///./nomi.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True,
                                    default=_uuid)
    handle: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # Explicit consent capture (privacy diligence):
    accepted_terms_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True)
    terms_version: Mapped[str | None] = mapped_column(String(16),
                                                      nullable=True)

    profile: Mapped["TasteProfileRow"] = relationship(
        back_populates="user", uselist=False,
        cascade="all, delete-orphan")
    tracks: Mapped[list["Track"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
    events: Mapped[list["FeedbackEventRow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class TasteProfileRow(Base):
    __tablename__ = "taste_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True,
                                    default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)  # TasteProfile dict
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now,
                                                 onupdate=_now)

    user: Mapped[User] = relationship(back_populates="profile")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True,
                                    default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), default="Untitled")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    # queued | generating | ready | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_prompt: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)

    backend_name: Mapped[str | None] = mapped_column(String(32),
                                                     nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64),
                                                      nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(400),
                                                   nullable=True)
    audio_format: Mapped[str | None] = mapped_column(String(8),
                                                     nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer,
                                                         nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="tracks")
    feedback: Mapped[list["FeedbackEventRow"]] = relationship(
        back_populates="track", cascade="all, delete-orphan")


class FeedbackEventRow(Base):
    __tablename__ = "feedback_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True,
                                    default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id"))
    event_type: Mapped[str] = mapped_column(String(24))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped[User] = relationship(back_populates="events")
    track: Mapped[Track] = relationship(back_populates="feedback")


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
