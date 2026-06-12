# Nomi Music — Architecture

**Status:** MVP Phase 1 · **Last updated:** June 2026

## What Nomi is, technically

Nomi Music is a personalized AI music product. The differentiating system is not the audio model — it is the **Taste Profile Engine**: a per-user, continuously-learning preference model that shapes every generation. Audio models are commodity components behind a stable adapter interface; the taste layer is proprietary.

This separation is deliberate and is the core architectural thesis: Nomi is **model-agnostic by design**. As foundation music models improve (or as licensing landscapes shift), Nomi swaps backends without touching product code, user data, or learned profiles.

## System overview

```
┌────────────┐     ┌─────────────────────────────────────────┐
│  Web App   │────▶│              Nomi Music API              │
│ (Next.js)  │     │                (FastAPI)                 │
└────────────┘     │                                          │
                   │  ┌──────────────┐   ┌────────────────┐  │
                   │  │ Taste Profile │──▶│ Prompt Compiler │  │
                   │  │    Engine     │   └───────┬────────┘  │
                   │  └──────▲───────┘           │ GenerationSpec
                   │         │ feedback   ┌──────▼────────┐   │
                   │         └────────────│  Backend       │   │
                   │                      │  Adapter       │   │
                   └──────────────────────┴──────┬─────────┴───┘
                                                 │
                          ┌──────────────────────┼──────────────┐
                          ▼                      ▼              ▼
                   ┌────────────┐      ┌──────────────┐   (future
                   │ MockBackend │      │ ACE-Step srv │    backends)
                   │ (stdlib,    │      │ (GPU host,   │
                   │  CI/demo)   │      │  Apache-2.0) │
                   └────────────┘      └──────────────┘
```

## Components

### 1. Taste Profile Engine (`backend/app/taste/engine.py`) — core IP

Per-user preference model over categorical dimensions (genre, mood, instrumentation; weights in [-1, 1]) and scalar dimensions (tempo, energy, vocal affinity; EWMA with confidence tracking).

Learning signals are behavioral events with calibrated rewards (save +1.25 … dislike −1.0). Updates use a saturating exponential moving average with a learning rate that decays on a 1/√n schedule — early signals move the profile quickly, mature profiles are stable but never frozen.

Engineering properties chosen for diligence:
- **Zero dependencies.** Pure Python; testable and auditable in isolation.
- **Explainable.** No opaque embeddings in v1 — every preference is a named, inspectable weight. (Embedding-based similarity is a roadmap item that will *augment*, not replace, the explainable layer.)
- **Deterministic and fully unit-tested** (19 tests, stdlib `unittest`).

### 2. Prompt Compiler (`backend/app/taste/compiler.py`)

Merges (profile + user's free-text prompt) into a backend-agnostic `GenerationSpec`. Key behaviors:
- Profile tags **supplement, never override**, the user's explicit request.
- Aversions become negative prompts.
- Scalar preferences apply only above a confidence threshold.
- A `personalization_strength` dial (0–1) lets users control Nomi's influence.
- Every spec carries a `personalization_trace` — an auditable record of exactly which profile dimensions shaped the output. Surfaced in the UI as "because you like…" and in demos as proof the personalization is real.

### 3. Generation backends (`backend/app/generation/backends.py`)

`GenerationBackend` interface: `GenerationSpec → GenerationResult (audio bytes + attributes + model version)`. Selected via `NOMI_GENERATION_BACKEND`.

| Backend | Purpose | Infra | Licensing posture |
|---|---|---|---|
| `mock` | Dev/CI/pipeline demos. Procedural stdlib synth producing real WAV audio that responds to tempo/energy/duration/prompt seed. | None | N/A (our code) |
| `ace_step` | Production generation. HTTP client to a self-hosted ACE-Step 1.5 inference server. | 1× CUDA GPU (3090-class sufficient; <10 s/song) | Apache-2.0 model; training-data provenance memo required — see LEGAL_COMPLIANCE.md |

The ACE-Step model never runs in the app process. It sits behind our own HTTP contract (`infra/acestep_server.py`) on a GPU host, so the app tier is GPU-free, horizontally scalable, and the model is independently upgradeable (including future Nomi-trained LoRAs — per-user style adapters are a natural Phase 4 extension that deepens the personalization moat).

### 4. API layer (`backend/app/main.py`)

FastAPI. Resource model: Users → TasteProfiles, Tracks, FeedbackEvents. Generation is async (202 + poll), executed off the request path. Privacy plumbing is built in from day one: explicit ToS consent capture at signup, full data export endpoint, and hard-delete endpoint cascading to all rows and audio files.

## MVP simplifications (explicit, with upgrade paths)

These are documented trade-offs, not oversights:

1. **Identity:** user-id parameter instead of real auth. The `current_user` dependency is the single seam; OAuth/session auth slots in there (Phase 3) with no route changes.
2. **Jobs:** FastAPI background tasks instead of a broker. The job function is queue-shaped; Redis + worker processes are a contained swap when concurrency demands it.
3. **Storage:** local-disk audio behind a path abstraction; S3/GCS driver is Phase 3.
4. **Database:** SQLite default for friction-free demos; Postgres via one env var (docker-compose ships it).

## Stack summary

Python 3.12 · FastAPI · SQLAlchemy 2 · Pydantic 2 · Postgres/SQLite · Next.js (Phase 2) · ACE-Step 1.5 on a CUDA host. All application dependencies are MIT/BSD/Apache-2.0 (see LICENSE_MANIFEST.md).
