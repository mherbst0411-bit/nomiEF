"""Nomi Music API.

FastAPI application wiring together the taste engine, prompt compiler and
generation backends.

MVP simplifications, documented for technical diligence (docs/ROADMAP.md):
  * Auth: each request identifies the user by id; real authentication
    (OAuth + sessions) is a Phase 3 item and the dependency boundary
    (`current_user`) is already in place to slot it in.
  * Jobs: generation runs in FastAPI background tasks. The interface is
    queue-shaped, so swapping in Redis/Celery for horizontal scale is a
    contained change.
  * Storage: audio is written to local disk (NOMI_AUDIO_DIR); the path
    abstraction allows an S3/GCS driver later.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import (BackgroundTasks, Depends, FastAPI, HTTPException)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import (FeedbackEventRow, TasteProfileRow, Track, User, get_session,
                 init_db)
from .generation.backends import get_backend
from .taste.compiler import compile_spec
from .taste.engine import (EVENT_REWARDS, FeedbackSignal, TasteProfile,
                           TrackAttributes)

AUDIO_DIR = Path(os.environ.get("NOMI_AUDIO_DIR", "./audio"))
TERMS_VERSION = "2026-06-draft"

app = FastAPI(
    title="Nomi Music API",
    version="0.1.0",
    description="Personalized AI music generation — music that knows you.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("NOMI_CORS_ORIGINS",
                                 "http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateUserIn(BaseModel):
    handle: str = Field(min_length=2, max_length=64)
    accept_terms: bool = Field(
        description="Explicit acceptance of ToS/Privacy Policy is required.")


class OnboardingIn(BaseModel):
    genres: list[str] = Field(default_factory=list, max_length=10)
    moods: list[str] = Field(default_factory=list, max_length=10)
    tempo_bpm: float | None = Field(default=None, ge=40, le=220)
    energy: float | None = Field(default=None, ge=0, le=1)
    prefers_vocals: bool | None = None


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=600)
    lyrics: str | None = Field(default=None, max_length=4000)
    duration_seconds: int = Field(default=90, ge=10, le=240)
    personalization_strength: float = Field(default=1.0, ge=0, le=1)
    title: str | None = Field(default=None, max_length=200)


class FeedbackIn(BaseModel):
    event_type: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def current_user(user_id: str, db: Session = Depends(get_session)) -> User:
    """MVP identity boundary. Replace with real auth in Phase 3 — every
    route already depends on this single function."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "user not found")
    return user


def _load_profile(db: Session, user: User) -> tuple[TasteProfileRow,
                                                    TasteProfile]:
    row = db.query(TasteProfileRow).filter_by(user_id=user.id).one_or_none()
    if row is None:
        row = TasteProfileRow(user_id=user.id, data={})
        db.add(row)
        db.commit()
        db.refresh(row)
    return row, TasteProfile.from_dict(row.data or {})


# ---------------------------------------------------------------------------
# Users & profiles
# ---------------------------------------------------------------------------

@app.post("/v1/users", status_code=201)
def create_user(body: CreateUserIn, db: Session = Depends(get_session)):
    if not body.accept_terms:
        raise HTTPException(400, "Terms must be accepted to create account.")
    if db.query(User).filter_by(handle=body.handle).one_or_none():
        raise HTTPException(409, "handle already taken")
    from .db import _now
    user = User(handle=body.handle, accepted_terms_at=_now(),
                terms_version=TERMS_VERSION)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "handle": user.handle,
            "terms_version": user.terms_version}


@app.post("/v1/users/{user_id}/onboarding")
def onboarding(body: OnboardingIn, user: User = Depends(current_user),
               db: Session = Depends(get_session)):
    row, profile = _load_profile(db, user)
    profile.seed_from_onboarding(
        genres=body.genres, moods=body.moods, tempo_bpm=body.tempo_bpm,
        energy=body.energy, prefers_vocals=body.prefers_vocals)
    row.data = profile.to_dict()
    db.commit()
    return {"profile": profile.to_dict(), "maturity": profile.maturity}


@app.get("/v1/users/{user_id}/profile")
def get_profile(user: User = Depends(current_user),
                db: Session = Depends(get_session)):
    _, profile = _load_profile(db, user)
    return {
        "profile": profile.to_dict(),
        "maturity": profile.maturity,
        "top": {
            "genres": profile.top("genres"),
            "moods": profile.top("moods"),
            "instruments": profile.top("instruments"),
        },
        "aversions": {
            "genres": profile.aversions("genres"),
            "moods": profile.aversions("moods"),
        },
    }


# -- privacy: export & delete (GDPR/CCPA plumbing) ---------------------------

@app.get("/v1/users/{user_id}/export")
def export_user_data(user: User = Depends(current_user),
                     db: Session = Depends(get_session)):
    """Full machine-readable export of the user's personal data."""
    _, profile = _load_profile(db, user)
    tracks = db.query(Track).filter_by(user_id=user.id).all()
    events = db.query(FeedbackEventRow).filter_by(user_id=user.id).all()
    return JSONResponse({
        "user": {"id": user.id, "handle": user.handle,
                 "created_at": str(user.created_at),
                 "terms_version": user.terms_version},
        "taste_profile": profile.to_dict(),
        "tracks": [{"id": t.id, "title": t.title, "prompt": t.user_prompt,
                    "created_at": str(t.created_at), "status": t.status}
                   for t in tracks],
        "feedback_events": [{"track_id": e.track_id, "type": e.event_type,
                             "at": str(e.created_at)} for e in events],
    })


@app.delete("/v1/users/{user_id}", status_code=204)
def delete_user(user: User = Depends(current_user),
                db: Session = Depends(get_session)):
    """Hard delete: account, profile, events, tracks and audio files."""
    for t in db.query(Track).filter_by(user_id=user.id).all():
        if t.audio_path and Path(t.audio_path).exists():
            Path(t.audio_path).unlink()
    db.delete(user)  # cascades to profile/tracks/events
    db.commit()


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _run_generation(track_id: str) -> None:
    """Background job: compile happens at request time; this executes the
    backend call and persists results."""
    from .db import SessionLocal
    db = SessionLocal()
    try:
        track = db.get(Track, track_id)
        if not track:
            return
        track.status = "generating"
        db.commit()

        from .taste.compiler import GenerationSpec
        spec = GenerationSpec(**{k: v for k, v in track.spec.items()})
        backend = get_backend()
        result = backend.generate(spec)

        path = AUDIO_DIR / f"{track.id}.{result.audio_format}"
        path.write_bytes(result.audio_bytes)

        track.audio_path = str(path)
        track.audio_format = result.audio_format
        track.backend_name = result.backend_name
        track.model_version = result.model_version
        track.attributes = result.attributes.__dict__
        track.duration_seconds = spec.duration_seconds
        track.status = "ready"
        db.commit()
    except Exception as exc:  # noqa: BLE001 — record any failure on the job
        track = db.get(Track, track_id)
        if track:
            track.status = "failed"
            track.error = f"{type(exc).__name__}: {exc}"
            db.commit()
    finally:
        db.close()


@app.post("/v1/users/{user_id}/generate", status_code=202)
def generate(body: GenerateIn, background: BackgroundTasks,
             user: User = Depends(current_user),
             db: Session = Depends(get_session)):
    _, profile = _load_profile(db, user)
    spec = compile_spec(
        profile, body.prompt, lyrics=body.lyrics,
        duration_seconds=body.duration_seconds,
        personalization_strength=body.personalization_strength)

    track = Track(user_id=user.id, user_prompt=body.prompt,
                  title=body.title or body.prompt[:60],
                  spec=spec.to_dict(), status="queued")
    db.add(track)
    db.commit()
    db.refresh(track)

    background.add_task(_run_generation, track.id)
    return {"track_id": track.id, "status": track.status,
            "personalization_trace": spec.personalization_trace}


@app.get("/v1/users/{user_id}/tracks")
def list_tracks(user: User = Depends(current_user),
                db: Session = Depends(get_session)):
    tracks = (db.query(Track).filter_by(user_id=user.id)
              .order_by(Track.created_at.desc()).all())
    return [{"id": t.id, "title": t.title, "status": t.status,
             "prompt": t.user_prompt, "backend": t.backend_name,
             "created_at": str(t.created_at),
             "personalization_trace":
                 (t.spec or {}).get("personalization_trace")}
            for t in tracks]


@app.get("/v1/users/{user_id}/tracks/{track_id}")
def get_track(track_id: str, user: User = Depends(current_user),
              db: Session = Depends(get_session)):
    t = db.get(Track, track_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "track not found")
    return {"id": t.id, "title": t.title, "status": t.status,
            "error": t.error, "prompt": t.user_prompt,
            "attributes": t.attributes, "backend": t.backend_name,
            "model_version": t.model_version,
            "audio_url": f"/v1/users/{user.id}/tracks/{t.id}/audio"
            if t.status == "ready" else None}


@app.get("/v1/users/{user_id}/tracks/{track_id}/audio")
def get_audio(track_id: str, user: User = Depends(current_user),
              db: Session = Depends(get_session)):
    t = db.get(Track, track_id)
    if not t or t.user_id != user.id or not t.audio_path:
        raise HTTPException(404, "audio not found")
    media = {"wav": "audio/wav", "mp3": "audio/mpeg",
             "flac": "audio/flac"}.get(t.audio_format or "wav", "audio/wav")
    return FileResponse(t.audio_path, media_type=media,
                        filename=f"{t.title}.{t.audio_format}")


# ---------------------------------------------------------------------------
# Feedback — closes the personalization loop
# ---------------------------------------------------------------------------

@app.post("/v1/users/{user_id}/tracks/{track_id}/feedback")
def feedback(track_id: str, body: FeedbackIn,
             user: User = Depends(current_user),
             db: Session = Depends(get_session)):
    if body.event_type not in EVENT_REWARDS:
        raise HTTPException(
            400, f"event_type must be one of {sorted(EVENT_REWARDS)}")
    t = db.get(Track, track_id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, "track not found")

    row, profile = _load_profile(db, user)
    attrs = TrackAttributes(**{
        k: v for k, v in (t.attributes or {}).items()
        if k in TrackAttributes.__dataclass_fields__})
    profile.apply(FeedbackSignal(event_type=body.event_type, track=attrs))
    row.data = profile.to_dict()

    db.add(FeedbackEventRow(user_id=user.id, track_id=t.id,
                            event_type=body.event_type))
    db.commit()
    return {"maturity": profile.maturity, "event_count": profile.event_count}


@app.get("/healthz")
def health():
    return {"ok": True, "backend":
            os.environ.get("NOMI_GENERATION_BACKEND", "mock")}
