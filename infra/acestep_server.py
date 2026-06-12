"""ACE-Step inference server (runs on the GPU host, not the app server).

A deliberately thin FastAPI wrapper around the Apache-2.0 ACE-Step
pipeline. The app layer (ACEStepBackend) talks only to this contract, so
the underlying model can be upgraded, fine-tuned (LoRA), or replaced
without touching product code.

Deploy on a CUDA host (3090/4090-class is sufficient; A100 for demo-day
latency):

    pip install -r infra/requirements-gpu.txt
    # Install ACE-Step per https://github.com/ace-step/ACE-Step-1.5
    uvicorn infra.acestep_server:app --host 0.0.0.0 --port 8001

Contract:
    POST /generate {prompt, negative_prompt?, lyrics?, duration_seconds}
        -> {job_id, audio_path, format, model_version}
    GET  /audio/{job_id}.wav -> audio bytes
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

OUTPUT_DIR = Path(os.environ.get("ACESTEP_OUTPUT_DIR", "./acestep_out"))
MODEL_VERSION = os.environ.get("ACESTEP_MODEL_VERSION", "ace-step-1.5")

app = FastAPI(title="Nomi ACE-Step Inference Server", version="0.1.0")

_pipeline = None  # lazy-loaded singleton


def _get_pipeline():
    """Load the ACE-Step pipeline once. Import is local so this module can
    be reviewed/tested on machines without the model installed."""
    global _pipeline
    if _pipeline is None:
        try:
            from acestep.pipeline_ace_step import ACEStepPipeline  # type: ignore
        except ImportError as exc:
            raise HTTPException(
                503, "ACE-Step is not installed on this host. See module "
                     "docstring for setup instructions.") from exc
        _pipeline = ACEStepPipeline(
            checkpoint_dir=os.environ.get("ACESTEP_CHECKPOINT_DIR"),
            dtype="bfloat16",
        )
    return _pipeline


class GenerateIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1200)
    negative_prompt: str | None = None
    lyrics: str | None = "[instrumental]"
    duration_seconds: int = Field(default=90, ge=10, le=600)


@app.on_event("startup")
def _startup() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/generate")
def generate(body: GenerateIn):
    pipeline = _get_pipeline()
    job_id = uuid.uuid4().hex
    out_path = OUTPUT_DIR / f"{job_id}.wav"

    # NOTE: argument names track the ACE-Step 1.5 pipeline API; pin the
    # model revision in requirements-gpu.txt and re-verify on upgrade.
    pipeline(
        prompt=body.prompt,
        lyrics=body.lyrics or "[instrumental]",
        audio_duration=body.duration_seconds,
        save_path=str(out_path),
    )
    if not out_path.exists():
        raise HTTPException(500, "generation produced no output file")

    return {"job_id": job_id, "audio_path": f"/audio/{job_id}.wav",
            "format": "wav", "model_version": MODEL_VERSION}


@app.get("/audio/{filename}")
def audio(filename: str):
    # Defense against path traversal: serve only flat .wav files we made.
    if "/" in filename or ".." in filename or not filename.endswith(".wav"):
        raise HTTPException(400, "invalid filename")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "not found")
    return FileResponse(path, media_type="audio/wav")


@app.get("/healthz")
def health():
    return {"ok": True, "model_version": MODEL_VERSION}
