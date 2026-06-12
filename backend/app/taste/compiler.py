"""Prompt Compiler.

Translates (TasteProfile + user's free-text request) into a structured,
backend-agnostic `GenerationSpec`. This is the second half of Nomi's core
IP: personalization is only valuable if it measurably shapes generation.

The compiler is deterministic and explainable: every spec carries a
`personalization_trace` describing exactly which profile dimensions
influenced the output — used in the UI ("because you like…") and in
investor demos to prove the taste engine is real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .engine import TasteProfile

DEFAULT_DURATION_SECONDS = 90
MAX_DURATION_SECONDS = 240


@dataclass
class GenerationSpec:
    """Backend-agnostic description of a track to generate."""

    prompt_tags: list[str]            # style tags fed to the model
    user_prompt: str                  # the user's own words, always preserved
    negative_tags: list[str] = field(default_factory=list)
    lyrics: Optional[str] = None      # None => instrumental
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    tempo_bpm: Optional[float] = None
    energy: Optional[float] = None
    want_vocals: bool = False
    personalization_trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "prompt_tags": self.prompt_tags,
            "user_prompt": self.user_prompt,
            "negative_tags": self.negative_tags,
            "lyrics": self.lyrics,
            "duration_seconds": self.duration_seconds,
            "tempo_bpm": self.tempo_bpm,
            "energy": self.energy,
            "want_vocals": self.want_vocals,
            "personalization_trace": self.personalization_trace,
        }


def compile_spec(profile: TasteProfile, user_prompt: str, *,
                 lyrics: Optional[str] = None,
                 duration_seconds: int = DEFAULT_DURATION_SECONDS,
                 personalization_strength: float = 1.0) -> GenerationSpec:
    """Build a GenerationSpec from a profile and a user request.

    `personalization_strength` in [0, 1] lets the user dial Nomi's
    influence up or down (1.0 = full personalization, 0.0 = prompt only).
    """
    strength = max(0.0, min(1.0, personalization_strength))
    trace: dict = {"strength": strength, "applied": []}

    tags: list[str] = []
    negative: list[str] = []

    if strength > 0:
        top_genres = profile.top("genres", k=2)
        top_moods = profile.top("moods", k=2)
        top_instruments = profile.top("instruments", k=2)

        # Don't fight the user: profile tags supplement, never override,
        # anything the user explicitly asked for.
        lowered = user_prompt.lower()
        for tag in top_genres + top_moods + top_instruments:
            if tag not in lowered:
                tags.append(tag)
        if top_genres:
            trace["applied"].append({"dimension": "genre", "tags": top_genres})
        if top_moods:
            trace["applied"].append({"dimension": "mood", "tags": top_moods})
        if top_instruments:
            trace["applied"].append(
                {"dimension": "instruments", "tags": top_instruments})

        for dim in ("genres", "moods"):
            av = profile.aversions(dim, k=2)
            negative.extend(a for a in av if a not in lowered)
        if negative:
            trace["applied"].append({"dimension": "aversions",
                                     "tags": list(negative)})

    tempo = None
    if strength > 0 and profile.tempo.value is not None \
            and profile.tempo.confidence >= 0.2:
        tempo = round(profile.tempo.value)
        trace["applied"].append({"dimension": "tempo_bpm", "value": tempo})

    energy = None
    if strength > 0 and profile.energy.value is not None \
            and profile.energy.confidence >= 0.2:
        energy = round(profile.energy.value, 2)
        trace["applied"].append({"dimension": "energy", "value": energy})

    want_vocals = bool(lyrics)
    if not lyrics and strength > 0 \
            and profile.vocal_affinity.value is not None \
            and profile.vocal_affinity.confidence >= 0.3 \
            and profile.vocal_affinity.value >= 0.6:
        want_vocals = True
        trace["applied"].append({"dimension": "vocals", "value": True})

    return GenerationSpec(
        prompt_tags=tags,
        user_prompt=user_prompt.strip(),
        negative_tags=negative,
        lyrics=lyrics,
        duration_seconds=min(int(duration_seconds), MAX_DURATION_SECONDS),
        tempo_bpm=tempo,
        energy=energy,
        want_vocals=want_vocals,
        personalization_trace=trace,
    )
