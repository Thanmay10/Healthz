# Cliniva — Consent-Gated AI Health Memory + Clinical Agents

Problem: doctors see 100+ patients with zero longitudinal history. Errors from forgotten allergies and drug interactions kill.

Solution: one Hindsight memory bank per patient shared by Scribe, Safety, Rx and Booking agents. AI drafts, doctor validates and signs, pharmacy verifies via QR.

## Quickstart (3 commands)

```
pip install -r backend/requirements.txt
python backend/seed.py
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/app/` — pick demo-001 (penicillin allergy, CONFLICT case) or demo-002 (safe case).

Run checks: `python test_e2e.py` (15 checks, all PASS).

## Architecture

- `backend/main.py` — FastAPI: consult / correct / sign / verify / timeline / fhir / abdm / auth / booking / ops
- `backend/safety.py` — RxNorm normalize, DDInter SQLite loader (`data/ddinter.sqlite` if mounted, else curated fallback), OpenFDA own-label, DailyMed citations, alternatives. Never guesses.
- `backend/scribe.py` + `audio_scribe.py` — transcript to SOAP + ICD-10 hints, mic-consent gate
- `memory/hindsight_client.py` — per-patient bank, retain / recall / reflect, mental models
- `backend/rx_sign.py` + `fhir.py` — JWT + sha256 signed Rx, QR PNG, ABDM FHIR R4 bundle
- `backend/auth.py`, `abdm.py`, `audit.py`, `ops.py`, `crypto_fields.py`, `config.py` — RBAC, consent artefacts, hash-chained audit, retention, booking, encryption
- `frontend/` — demo UI (PWA manifest included)

## Demo (3 min)

1. Load timeline for demo-001, try revoked ON to prove locking.
2. Run throat consult — red CONFLICT with citation + azithromycin alternative.
3. Apply correction — mental model `avoid-penicillin-class` appears, recheck SAFE, booking suggests Saturday.
4. Sign — QR + verify VALID, tamper demo FAILS, FHIR downloads, audit shows trail.

## APIs used

RxNorm REST, openFDA drug labels, DailyMed (citations), Hindsight retain/recall/reflect, Azure-ready (Speech, OpenAI, Key Vault, Health Data Services via env flags).

## Disclaimer

Prototype. Supports, does not replace clinical judgment. Doctor validation mandatory.
