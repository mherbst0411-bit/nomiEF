# Nomi Music — Legal & Compliance Framework

**Status:** Working framework — NOT legal advice. Every item marked
**[COUNSEL]** requires review by qualified attorneys before launch,
fundraising representations, or acquisition diligence.
**Last updated:** June 2026

This document is structured the way an acquirer's legal diligence team will
ask the questions.

---

## 1. AI model & training data rights

The single most scrutinized issue for AI music companies (see the 2024 RIAA
litigation against major generation platforms).

**Nomi's posture:** Nomi does not train a foundation audio model and does not
scrape or ingest copyrighted recordings. Generation uses ACE-Step 1.5,
self-hosted under its **Apache-2.0 license**, which permits commercial use of
the model and outputs at the license level.

**Key distinction to document for diligence:** the *model license*
(Apache-2.0 — clear) and the *training-data provenance* (described by the
model authors as licensed audio in their published paper) are separate
questions. Provenance representations are the model authors', not ours.

- **[COUNSEL]** Commission a short memo: review ACE-Step's published
  training-data disclosures; assess residual risk of deploying outputs
  commercially in the US; document the analysis. This memo *is* a diligence
  asset — having it ready signals maturity.
- **Engineering control:** the model revision is pinned; every generated
  track records `backend_name` + `model_version`, giving a complete
  provenance trail per output. If a backend ever becomes legally
  problematic, affected outputs are identifiable and the backend is
  swappable (adapter architecture).
- **Rejected alternatives, for the record:** MusicGen (weights CC BY-NC —
  no commercial use even self-hosted); third-party generation APIs
  (dependency on a competitor + their unresolved training-data exposure
  becomes our diligence problem).

## 2. Ownership & rights in AI-generated outputs

Under current US Copyright Office guidance, works generated wholly by AI
without sufficient human authorship are not copyrightable. Implications:

- **ToS must not promise users "ownership" of copyright in generated
  tracks.** Correct framing: Nomi grants users a broad, perpetual,
  royalty-free license to use, distribute and monetize their generated
  tracks, and Nomi claims no exclusivity over them.
- User-supplied lyrics are human authorship the user retains; the ToS should
  have the user license lyrics to Nomi solely to perform the generation.
- **[COUNSEL]** Draft ToS language on output rights; revisit as Copyright
  Office guidance evolves (human-contribution thresholds are actively
  developing).

## 3. User-uploaded vocal content (Pillar 2) — highest-risk area

- **Upload warranties:** user represents they own or control all rights in
  the uploaded recording and the performance embodied in it, and that it
  contains no third party's voice without authorization.
- **Voice as biometric data:** voiceprints can qualify as biometric
  identifiers. **Illinois BIPA is directly relevant (Nomi is
  Chicago-based)** and carries a private right of action with statutory
  damages. Mitigations to build in: we process audio as audio (no speaker
  identification/voiceprint extraction), written consent at upload, a
  published retention-and-destruction schedule, and deletion on request.
  - **[COUNSEL — priority]** BIPA analysis *before* Pillar 2 ships, plus
    Washington MHMD / Texas CUBI / Colorado-Virginia biometric provisions.
- **Anti-impersonation:** prohibit uploading another person's voice;
  Tennessee's ELVIS Act and similar voice-likeness statutes are spreading.
  **[COUNSEL]** AUP language.
- **No voice cloning in MVP scope.** Pillar 2 is *enhancement of the user's
  own recording* (cleanup, mix, master). This boundary is deliberate; do not
  cross it without a dedicated legal review.

## 4. Privacy & data protection

- Taste profiles are personal data (behavioral preference data). Engineering
  controls already implemented: explicit ToS consent capture with version
  stamping at signup; full machine-readable export endpoint; hard-delete
  endpoint cascading account → profile → events → tracks → audio files.
- Posture: 13+ minimum age (COPPA); CCPA/CPRA readiness (CA users);
  GDPR-shaped rights handling by default (export/delete) even pre-EU launch.
- **[COUNSEL]** Privacy Policy + ToS drafting; state-law applicability
  review (IL, CA at minimum); DPA template for any processors.

## 5. Open-source license hygiene

- Policy: **permissive licenses only (MIT/BSD/Apache-2.0)** in proprietary
  code. No GPL/AGPL/LGPL.
- Known traps documented and avoided: Matchering (GPL-3.0) and Spotify
  pedalboard (GPL-3.0) are *excluded* from the Pillar 2 plan despite being
  the popular choices; Demucs (MIT) is approved for stem separation.
- Enforcement: `docs/LICENSE_MANIFEST.md` + automated license scan in CI
  (Phase 2). An auditable manifest is a standard acquirer ask.

## 6. Trademark — "NOMI MUSIC" (pending filing)

Filing covers **AI-generated, personalized music software**.

- **Pillar 1 (personalized generation): squarely within scope.** Product
  language is built to *reinforce* the filing: the taste engine is branded
  the "Nomi Profile"; UI copy and API descriptions use "personalized AI
  music" phrasing ("music that knows you"); profile maturity states surface
  the personalization claim in-product. Documented use consistent with the
  description strengthens the application.
- **Pillar 2 (vocal cleanup/mix/master of user recordings): likely OUTSIDE
  the current description** — the output is the user's own recording
  enhanced, not AI-generated personalized music. **[COUNSEL — flagged per
  founder request]** Evaluate amending/expanding coverage (or a companion
  application) for audio processing/editing/mastering software (Int'l
  Classes 9/42) before Pillar 2 is marketed. Interim mitigation: Pillar 2 is
  presented as a *feature within* Nomi Music ("Nomi Studio" naming deferred
  pending counsel), never as a separately branded product.
- Engineering support: user-facing strings centralized so terminology stays
  consistent with whatever counsel approves.

## 7. Regulatory / disclosure items

- **AI transparency:** generated tracks are labeled as AI-generated in the
  product and metadata (`backend_name`, `model_version` on every track).
  Watch state AI-disclosure laws (e.g., CA AI Transparency Act) for labeling
  obligations as distribution features arrive. **[COUNSEL]** before adding
  any "distribute to streaming" feature — DSPs also impose their own
  AI-content policies.
- **Content moderation:** prompt/lyric filtering for unlawful content is a
  Phase 3 engineering item; AUP is part of the ToS package.

---

## Counsel engagement checklist (priority order)

1. BIPA / biometric review for Pillar 2 (before any vocal-upload feature ships)
2. ToS + Privacy Policy + AUP package
3. ACE-Step training-data provenance memo
4. Trademark scope review re: Pillar 2; possible expanded filing
5. Output-rights language review (ongoing as USCO guidance evolves)

## Standing diligence artifacts this repo maintains

- License manifest (LICENSE_MANIFEST.md) — every dependency + license
- Model provenance trail — backend/model version on every generated track
- Consent records — ToS version + timestamp on every account
- Privacy plumbing — export & hard-delete endpoints, tested
