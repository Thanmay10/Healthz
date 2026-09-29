"""Append-only audit log (DPDP/ABDM evidence). JSONL at data/audit.jsonl"""
import json
import pathlib
import time

AUDIT = pathlib.Path(__file__).resolve().parent.parent / "data" / "audit.jsonl"


def log(event: str, patient_id: str = "", actor: str = "", detail: dict | None = None) -> dict:
    rec = {"ts": int(time.time()), "event": event, "patient_id": patient_id, "actor": actor, "detail": detail or {}}
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_all(limit: int = 100) -> list:
    if not AUDIT.exists():
        return []
    lines = AUDIT.read_text(encoding="utf-8").strip().split("\n")
    out = []
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def dpdp_notice(purpose: str = "OPD consultation at Cliniva Demo Clinic") -> dict:
    return {
        "title": "How we use your health data (DPDP Notice)",
        "language": ["en", "hi (on request)"],
        "collects": ["name, age, ABHA ID", "allergies, conditions, prescriptions", "consult transcript (with mic consent)"],
        "purposes": [purpose, "safety check (allergy/drug-interaction)", "follow-up reminders"],
        "sharing": "Only with treating doctor/pharmacy via ABDM HIE-CM consent artefact. Never for marketing.",
        "rights": "Access summary, correct errors, withdraw consent as easily as giving it. Withdrawal locks timeline.",
        "retention": "Clinical records kept per medical law (3-10y); marketing/analytics erased on request.",
        "contact": "Data Protection Officer: dpo@cliniva.demo | Grievance: 30-day SLA | Board: Data Protection Board of India",
        "storage": "India (Mumbai region), AES-256 at rest, TLS 1.3 in transit, immutable audit logs",
    }
