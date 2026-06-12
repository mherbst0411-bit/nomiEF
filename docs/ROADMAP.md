# Roadmap to Demo-Ready (end of summer 2026)

## Phase 1 — Core engine + API (DONE, this drop)
Taste Profile Engine, Prompt Compiler, backend adapter (mock + ACE-Step),
full API (users/onboarding/generate/feedback/library/privacy), 19-test
suite, docker-compose, diligence docs.

## Phase 2 — Frontend + real model (frontend DELIVERED; GPU bring-up remains)
Next.js web app: onboarding quiz, prompt studio, library + audio player,
feedback UI, "Nomi Profile" visualization with personalization traces.
Stand up ACE-Step on a rented GPU (RunPod/Lambda, 3090/4090-class,
~$0.30–0.50/hr); integration tests against the real model. CI with license
scanning.

## Phase 3 — Hardening (≈3 weeks)
Real auth (OAuth + sessions at the `current_user` seam), Redis job queue +
workers, S3 audio storage, rate limiting, prompt/lyric content filtering,
structured logging + metrics, staging deploy.

## Phase 4 — Pillar 2 vocal studio (≈3–4 weeks, gated on BIPA counsel review)
Upload pipeline (consent + warranties at upload), Demucs stem separation,
permissively-licensed DSP chain (denoise, de-ess, EQ, compression),
loudness-normalized mastering to −14 LUFS streaming target, A/B
before/after player.

## Phase 5 — Pitch package (≈1 week)
Demo script + seeded demo accounts with mature taste profiles, technical
diligence binder (architecture, license manifest, provenance memo, test
reports), per-user LoRA personalization prototype if GPU time allows.
