"""Nomi Taste Profile Engine.

This module is the core intellectual property of Nomi Music: a per-user,
continuously-learning model of musical taste. It is deliberately written in
pure Python with zero third-party dependencies so that:

  1. It is trivially unit-testable and auditable (technical due diligence).
  2. It is portable across backends (API server, batch jobs, edge).
  3. The learning logic is explicit and explainable — no black box.

Design
------
A `TasteProfile` is a set of weighted preference dimensions:

  * Categorical dimensions (genre, mood, instrumentation): tag -> weight
    in [-1.0, 1.0], where positive means affinity and negative aversion.
  * Scalar dimensions (tempo, energy, vocal affinity): exponentially
    weighted moving averages with confidence tracking.

The profile is updated from `FeedbackSignal`s — behavioral events such as
likes, skips, saves, full listens, and regenerations — each carrying the
attributes of the track the user reacted to. Updates use an exponential
moving average so recent behavior matters more, with a learning rate that
decays as confidence grows (early signals move the profile a lot; a mature
profile is stable).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Signal definitions
# ---------------------------------------------------------------------------

#: Reward associated with each behavioral event type. Positive events pull
#: the profile toward the track's attributes; negative events push away.
EVENT_REWARDS: dict[str, float] = {
    "like": 1.0,
    "save": 1.25,        # saving to library is the strongest positive signal
    "share": 1.1,
    "full_listen": 0.45, # listened to >=90% of the track
    "partial_listen": 0.1,
    "regenerate": -0.35, # asked for another take: mild dissatisfaction
    "skip": -0.6,        # skipped early (<30%)
    "dislike": -1.0,
}

#: Base learning rate before confidence decay.
BASE_LEARNING_RATE = 0.18

#: Floor so a mature profile never becomes completely frozen.
MIN_LEARNING_RATE = 0.03


@dataclass
class TrackAttributes:
    """The musical attributes of a generated track, as recorded at
    generation time. These are what feedback events are *about*."""

    genres: list[str] = field(default_factory=list)
    moods: list[str] = field(default_factory=list)
    instruments: list[str] = field(default_factory=list)
    tempo_bpm: Optional[float] = None
    energy: Optional[float] = None          # 0.0 (calm) .. 1.0 (intense)
    has_vocals: Optional[bool] = None


@dataclass
class FeedbackSignal:
    """A single behavioral event from a user about a track."""

    event_type: str
    track: TrackAttributes
    timestamp: float = field(default_factory=time.time)

    @property
    def reward(self) -> float:
        try:
            return EVENT_REWARDS[self.event_type]
        except KeyError:
            raise ValueError(
                f"Unknown event type {self.event_type!r}; "
                f"expected one of {sorted(EVENT_REWARDS)}"
            )


# ---------------------------------------------------------------------------
# Scalar preference with confidence
# ---------------------------------------------------------------------------

@dataclass
class ScalarPreference:
    """An EWMA estimate of a scalar preference (e.g. preferred tempo)."""

    value: Optional[float] = None
    confidence: float = 0.0  # 0.0 .. 1.0, grows with positive observations

    def observe(self, observed: float, reward: float, lr: float) -> None:
        """Update toward `observed` when reward is positive; away when
        negative (only if we already have an estimate)."""
        if reward > 0:
            if self.value is None:
                self.value = observed
            else:
                step = lr * reward
                self.value = (1 - step) * self.value + step * observed
            self.confidence = min(1.0, self.confidence + lr * reward * 0.5)
        elif reward < 0 and self.value is not None:
            # Push gently away from the disliked observation.
            delta = self.value - observed
            self.value = self.value + lr * abs(reward) * 0.5 * _sign(delta)
            self.confidence = max(0.0, self.confidence - lr * 0.1)

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": round(self.confidence, 4)}

    @classmethod
    def from_dict(cls, d: dict) -> "ScalarPreference":
        return cls(value=d.get("value"), confidence=d.get("confidence", 0.0))


def _sign(x: float) -> float:
    if x > 0:
        return 1.0
    if x < 0:
        return -1.0
    return 1.0  # arbitrary direction when exactly equal


# ---------------------------------------------------------------------------
# Taste profile
# ---------------------------------------------------------------------------

@dataclass
class TasteProfile:
    """A user's learned musical taste."""

    genres: dict[str, float] = field(default_factory=dict)
    moods: dict[str, float] = field(default_factory=dict)
    instruments: dict[str, float] = field(default_factory=dict)
    tempo: ScalarPreference = field(default_factory=ScalarPreference)
    energy: ScalarPreference = field(default_factory=ScalarPreference)
    vocal_affinity: ScalarPreference = field(default_factory=ScalarPreference)
    event_count: int = 0

    # -- learning ----------------------------------------------------------

    @property
    def learning_rate(self) -> float:
        """Learning rate decays with experience: 1/sqrt schedule with floor."""
        decayed = BASE_LEARNING_RATE / math.sqrt(1 + self.event_count / 25)
        return max(MIN_LEARNING_RATE, decayed)

    def apply(self, signal: FeedbackSignal) -> None:
        """Apply one feedback signal to the profile (in place)."""
        reward = signal.reward
        lr = self.learning_rate
        track = signal.track

        for tag in track.genres:
            _update_tag(self.genres, tag, reward, lr)
        for tag in track.moods:
            _update_tag(self.moods, tag, reward, lr)
        for tag in track.instruments:
            _update_tag(self.instruments, tag, reward, lr)

        if track.tempo_bpm is not None:
            self.tempo.observe(track.tempo_bpm, reward, lr)
        if track.energy is not None:
            self.energy.observe(track.energy, reward, lr)
        if track.has_vocals is not None:
            self.vocal_affinity.observe(1.0 if track.has_vocals else 0.0,
                                        reward, lr)

        self.event_count += 1

    def seed_from_onboarding(self, *, genres: list[str], moods: list[str],
                             tempo_bpm: Optional[float] = None,
                             energy: Optional[float] = None,
                             prefers_vocals: Optional[bool] = None) -> None:
        """Initialize the profile from explicit onboarding answers.

        Onboarding choices are strong, intentional signals; we seed them at
        a moderate positive weight rather than 1.0 so behavior can still
        reshape the profile quickly.
        """
        for g in genres:
            self.genres[_norm(g)] = max(self.genres.get(_norm(g), 0.0), 0.55)
        for m in moods:
            self.moods[_norm(m)] = max(self.moods.get(_norm(m), 0.0), 0.55)
        if tempo_bpm is not None:
            self.tempo = ScalarPreference(value=tempo_bpm, confidence=0.3)
        if energy is not None:
            self.energy = ScalarPreference(value=energy, confidence=0.3)
        if prefers_vocals is not None:
            self.vocal_affinity = ScalarPreference(
                value=1.0 if prefers_vocals else 0.0, confidence=0.3)

    # -- reading the profile -------------------------------------------------

    def top(self, dimension: str, k: int = 3,
            threshold: float = 0.05) -> list[str]:
        """Top-k positively weighted tags for a categorical dimension."""
        weights: dict[str, float] = getattr(self, dimension)
        ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        return [tag for tag, w in ranked[:k] if w > threshold]

    def aversions(self, dimension: str, k: int = 3,
                  threshold: float = -0.25) -> list[str]:
        """Tags the user actively dislikes."""
        weights: dict[str, float] = getattr(self, dimension)
        ranked = sorted(weights.items(), key=lambda kv: kv[1])
        return [tag for tag, w in ranked[:k] if w < threshold]

    @property
    def maturity(self) -> str:
        """Human-readable profile maturity, surfaced in the UI."""
        if self.event_count < 5:
            return "getting to know you"
        if self.event_count < 30:
            return "learning your taste"
        return "knows you"

    # -- (de)serialization ---------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "genres": {k: round(v, 4) for k, v in self.genres.items()},
            "moods": {k: round(v, 4) for k, v in self.moods.items()},
            "instruments": {k: round(v, 4) for k, v in self.instruments.items()},
            "tempo": self.tempo.to_dict(),
            "energy": self.energy.to_dict(),
            "vocal_affinity": self.vocal_affinity.to_dict(),
            "event_count": self.event_count,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "TasteProfile":
        return cls(
            genres=dict(d.get("genres", {})),
            moods=dict(d.get("moods", {})),
            instruments=dict(d.get("instruments", {})),
            tempo=ScalarPreference.from_dict(d.get("tempo", {})),
            energy=ScalarPreference.from_dict(d.get("energy", {})),
            vocal_affinity=ScalarPreference.from_dict(
                d.get("vocal_affinity", {})),
            event_count=d.get("event_count", 0),
        )

    @classmethod
    def from_json(cls, s: str) -> "TasteProfile":
        return cls.from_dict(json.loads(s))


def _update_tag(weights: dict[str, float], tag: str,
                reward: float, lr: float) -> None:
    tag = _norm(tag)
    current = weights.get(tag, 0.0)
    updated = current + lr * reward * (1 - abs(current))  # saturating update
    weights[tag] = max(-1.0, min(1.0, updated))


def _norm(tag: str) -> str:
    return tag.strip().lower()
