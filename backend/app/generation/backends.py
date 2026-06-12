"""Generation backends.

Nomi is model-agnostic by design. Every audio model sits behind the
`GenerationBackend` interface; the rest of the system only ever sees a
`GenerationSpec` in and an audio file + `TrackAttributes` out.

Backends in this MVP:

  * MockBackend       — deterministic stdlib synthesizer. Produces real,
                        playable WAV audio shaped by the spec (tempo,
                        energy, duration). Zero dependencies, zero GPU.
                        Used for local dev, CI, and pipeline demos.
  * ACEStepBackend    — HTTP client for a self-hosted ACE-Step inference
                        server (see infra/acestep_server.py). Apache-2.0
                        model, commercially usable; see
                        docs/LEGAL_COMPLIANCE.md before production use.

Selection is by environment variable NOMI_GENERATION_BACKEND
("mock" | "ace_step"), resolved in `get_backend()`.
"""

from __future__ import annotations

import abc
import hashlib
import io
import math
import os
import struct
import wave
from dataclasses import dataclass

from ..taste.compiler import GenerationSpec
from ..taste.engine import TrackAttributes


@dataclass
class GenerationResult:
    audio_bytes: bytes
    audio_format: str               # "wav" | "mp3" | "flac"
    attributes: TrackAttributes     # what was actually generated
    backend_name: str
    model_version: str


class GenerationBackend(abc.ABC):
    """Interface every audio model adapter must implement."""

    name: str = "abstract"

    @abc.abstractmethod
    def generate(self, spec: GenerationSpec) -> GenerationResult:
        """Synchronously generate audio for a spec. Called from the job
        worker, never from a request handler."""


# ---------------------------------------------------------------------------
# Mock backend — real audio, no model
# ---------------------------------------------------------------------------

class MockBackend(GenerationBackend):
    """Deterministic procedural synthesizer.

    This is intentionally simple music — a chord progression with a beat —
    but it is *real audio that responds to the spec*: tempo follows
    spec.tempo_bpm, brightness/drive follow spec.energy, length follows
    spec.duration_seconds, and the harmonic seed is derived from the
    prompt so different prompts sound different. That makes the entire
    product loop (profile -> compile -> generate -> listen -> feedback ->
    profile update) demonstrable end-to-end with no GPU.
    """

    name = "mock"
    SAMPLE_RATE = 22050

    def generate(self, spec: GenerationSpec) -> GenerationResult:
        seed = int.from_bytes(
            hashlib.sha256(
                (spec.user_prompt + ",".join(spec.prompt_tags)).encode()
            ).digest()[:4], "big")
        tempo = spec.tempo_bpm or 100.0
        energy = spec.energy if spec.energy is not None else 0.5
        duration = max(8, min(spec.duration_seconds, 30))  # keep mock short

        audio = self._render(seed, tempo, energy, duration)

        attrs = TrackAttributes(
            genres=spec.prompt_tags[:2] or ["electronic"],
            moods=spec.prompt_tags[2:4] or ["neutral"],
            instruments=["synth", "drums"],
            tempo_bpm=tempo,
            energy=energy,
            has_vocals=False,  # the mock never sings (mercifully)
        )
        return GenerationResult(
            audio_bytes=audio,
            audio_format="wav",
            attributes=attrs,
            backend_name=self.name,
            model_version="mock-1.0",
        )

    # -- synthesis ----------------------------------------------------------

    # A small palette of pleasant progressions (semitone offsets from root).
    PROGRESSIONS = [
        [0, 5, 7, 5],      # I-IV-V-IV
        [0, 9, 5, 7],      # I-vi-IV-V
        [0, 7, 9, 5],      # I-V-vi-IV (the pop classic)
        [0, 3, 5, 7],      # minor-ish walk
    ]

    def _render(self, seed: int, tempo: float, energy: float,
                duration: int) -> bytes:
        sr = self.SAMPLE_RATE
        n = sr * duration
        root_hz = 220.0 * (2 ** ((seed % 12) / 12))
        progression = self.PROGRESSIONS[(seed >> 4) % len(self.PROGRESSIONS)]
        beat_period = 60.0 / max(60.0, min(tempo, 180.0))
        bar = beat_period * 4

        samples = bytearray()
        for i in range(n):
            t = i / sr
            chord_root = root_hz * (2 ** (
                progression[int(t // bar) % len(progression)] / 12))
            # Triad
            s = 0.0
            for interval, amp in ((0, 0.5), (4, 0.3), (7, 0.3)):
                f = chord_root * (2 ** (interval / 12))
                s += amp * math.sin(2 * math.pi * f * t)
            # Brightness with energy: add an octave shimmer
            s += energy * 0.2 * math.sin(2 * math.pi * chord_root * 2 * t)
            # Beat: amplitude pulse + noise tick
            phase = (t % beat_period) / beat_period
            pulse = 0.55 + 0.45 * math.exp(-6 * phase)
            tick = (0.25 + 0.5 * energy) * math.exp(-40 * phase) * \
                ((seed * 1103515245 + i) % 2000 / 1000 - 1)
            s = (s * pulse * (0.4 + 0.4 * energy)) + tick * 0.15
            # Gentle master fade in/out
            fade = min(1.0, t / 1.5, (duration - t) / 2.0)
            s = max(-1.0, min(1.0, s * fade))
            samples += struct.pack("<h", int(s * 32767 * 0.8))

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(bytes(samples))
        return buf.getvalue()


# ---------------------------------------------------------------------------
# ACE-Step backend — self-hosted inference server client
# ---------------------------------------------------------------------------

class ACEStepBackend(GenerationBackend):
    """Client for a self-hosted ACE-Step inference server.

    The server (infra/acestep_server.py) is a thin FastAPI wrapper around
    the Apache-2.0 ACE-Step pipeline, deployed on a GPU host. Keeping the
    model behind our own HTTP contract means the app layer has zero GPU
    dependencies and the model can be swapped or upgraded independently.
    """

    name = "ace_step"

    def __init__(self, base_url: str | None = None,
                 timeout_seconds: int = 300):
        self.base_url = (base_url
                         or os.environ.get("ACESTEP_URL",
                                           "http://localhost:8001")
                         ).rstrip("/")
        self.timeout = timeout_seconds

    def generate(self, spec: GenerationSpec) -> GenerationResult:
        import httpx  # imported lazily; not needed for mock-only installs

        tags = list(spec.prompt_tags)
        if spec.user_prompt:
            tags.insert(0, spec.user_prompt)
        if spec.tempo_bpm:
            tags.append(f"{int(spec.tempo_bpm)} bpm")

        payload = {
            "prompt": ", ".join(tags),
            "negative_prompt": ", ".join(spec.negative_tags) or None,
            "lyrics": spec.lyrics if spec.want_vocals else "[instrumental]",
            "duration_seconds": spec.duration_seconds,
        }
        resp = httpx.post(f"{self.base_url}/generate", json=payload,
                          timeout=self.timeout)
        resp.raise_for_status()
        meta = resp.json()

        audio_resp = httpx.get(f"{self.base_url}{meta['audio_path']}",
                               timeout=self.timeout)
        audio_resp.raise_for_status()

        attrs = TrackAttributes(
            genres=spec.prompt_tags[:2],
            moods=spec.prompt_tags[2:4],
            instruments=[],
            tempo_bpm=spec.tempo_bpm,
            energy=spec.energy,
            has_vocals=spec.want_vocals,
        )
        return GenerationResult(
            audio_bytes=audio_resp.content,
            audio_format=meta.get("format", "wav"),
            attributes=attrs,
            backend_name=self.name,
            model_version=meta.get("model_version", "ace-step-1.5"),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_BACKENDS = {
    "mock": MockBackend,
    "ace_step": ACEStepBackend,
}


def get_backend(name: str | None = None) -> GenerationBackend:
    name = name or os.environ.get("NOMI_GENERATION_BACKEND", "mock")
    try:
        return _BACKENDS[name]()
    except KeyError:
        raise ValueError(
            f"Unknown backend {name!r}; expected one of {sorted(_BACKENDS)}")
