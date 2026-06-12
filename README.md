# Nomi Music

**Personalized AI music generation — music that knows you.**

Nomi learns each user's musical taste from behavior (likes, saves, skips,
listen-through) and explicit onboarding, builds a continuously-evolving
**Nomi Profile**, and uses it to shape every AI-generated track. The audio
model is a swappable component; the taste layer is the product.

## Run the whole app — one command

**With Docker (web + API + Postgres):**

```bash
docker compose up --build
# web:  http://localhost:3000
# api:  http://localhost:8000/docs
```

**Without Docker (SQLite, hot reload):**

```bash
./dev.sh
```

`dev.sh` creates the backend venv, installs both sides' dependencies on
first run, starts the API on :8000 and the Next.js app on :3000.

Flow: pick a handle → onboarding quiz seeds your Nomi Profile → Studio:
describe a track, watch it generate, listen, react. Every save/like/skip
visibly reshapes the resonance bars, each track shows teal "because you
like…" chips from its personalization trace, and the Account menu gives
you one-click data export and hard delete.

## Quick start (API only, no GPU required)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then exercise the full loop:

```bash
# 1. Create a user (explicit ToS consent is required by the API)
curl -s -X POST localhost:8000/v1/users \
  -H 'content-type: application/json' \
  -d '{"handle":"max","accept_terms":true}'
# -> {"id":"<USER_ID>", ...}

# 2. Onboard taste
curl -s -X POST "localhost:8000/v1/users/<USER_ID>/onboarding" \
  -H 'content-type: application/json' \
  -d '{"genres":["lo-fi","jazz"],"moods":["chill"],"tempo_bpm":85,"energy":0.35}'

# 3. Generate (mock backend renders real, playable WAV — no GPU)
curl -s -X POST "localhost:8000/v1/users/<USER_ID>/generate" \
  -H 'content-type: application/json' \
  -d '{"prompt":"something mellow for late-night coding"}'
# -> {"track_id":"<TRACK_ID>","personalization_trace":{...}}

# 4. Listen
curl -s "localhost:8000/v1/users/<USER_ID>/tracks/<TRACK_ID>/audio" -o track.wav

# 5. Close the loop — feedback updates the Nomi Profile
curl -s -X POST "localhost:8000/v1/users/<USER_ID>/tracks/<TRACK_ID>/feedback" \
  -H 'content-type: application/json' -d '{"event_type":"save"}'
```

Interactive API docs: http://localhost:8000/docs

## Web app only (frontend/)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://localhost:8000
npm run dev                        # http://localhost:3000
```

## Switching to the real model

Deploy `infra/acestep_server.py` on a CUDA host (ACE-Step 1.5, Apache-2.0;
<10 s per song on an RTX 3090), then:

```bash
export NOMI_GENERATION_BACKEND=ace_step ACESTEP_URL=http://<gpu-host>:8001
```

## Tests

```bash
python3 -m unittest discover -s backend/tests -t .
```

19 tests, stdlib-only, no install required for the core engine.

## Documentation

- `docs/ARCHITECTURE.md` — system design and decision record
- `docs/LEGAL_COMPLIANCE.md` — legal/IP framework with counsel flags
- `docs/LICENSE_MANIFEST.md` — dependency license audit
- `docs/ROADMAP.md` — path to demo-ready

© 2026 Nomi AI, LLC. Proprietary.
