# Dependency License Manifest

Policy: permissive licenses only (MIT / BSD / Apache-2.0) in proprietary
code. CI enforcement via `pip-licenses --fail-on="GPL;LGPL;AGPL"` (Phase 2).

## Application (backend/requirements.txt)
| Package | License | Role |
|---|---|---|
| fastapi | MIT | API framework |
| uvicorn | BSD-3-Clause | ASGI server |
| sqlalchemy | MIT | ORM |
| pydantic | MIT | Validation |
| httpx | BSD-3-Clause | Backend HTTP client |
| python-multipart | Apache-2.0 | Uploads (Pillar 2) |

## Models / GPU host
| Component | License | Notes |
|---|---|---|
| ACE-Step 1.5 | Apache-2.0 | Self-hosted generation model. Provenance memo: see LEGAL_COMPLIANCE.md §1 |
| Demucs (planned, Pillar 2) | MIT | Stem separation |

## Evaluated and REJECTED on license grounds
| Component | License | Reason |
|---|---|---|
| MusicGen weights | CC BY-NC 4.0 | Non-commercial only |
| Matchering | GPL-3.0 | Copyleft contamination |
| pedalboard (Spotify) | GPL-3.0 | Copyleft contamination |
