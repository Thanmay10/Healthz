"""ABDM client: mock default, sandbox/prod via env. HIP/HIU FHIR + HIE-CM consent artefact model."""
import time
import uuid
from backend.config import ABDM_MODE, ABDM_SANDBOX


def consent_artefact(patient_abha: str, hiu_id: str, hip_id: str, purpose: str, records: list, hours: int = 24) -> dict:
    now = int(time.time())
    return {
        "artefact_id": str(uuid.uuid4())[:12],
        "mode": ABDM_MODE,
        "patient_abha": patient_abha,
        "hiu": hiu_id,
        "hip": hip_id,
        "purpose": purpose,
        "records": records,
        "valid_from": now,
        "valid_until": now + hours * 3600,
        "status": "GRANTED-mock" if ABDM_MODE == "mock" else "REQUESTED",
        "sandbox": ABDM_SANDBOX,
        "note": "Mock artefact for demo. In sandbox: POST /consent/request via HIE-CM, patient approves in PHR app, HIP validates signed artefact then releases FHIR bundle.",
    }


def hip_release_bundle(artefact: dict, fhir_bundle: dict) -> dict:
    if artefact.get("status", "").startswith("GRANTED") or ABDM_MODE == "mock":
        return {"released": True, "bundle_id": fhir_bundle.get("id"), "via": "HIP->HIU (mock mTLS)"}
    return {"released": False, "reason": "Consent not granted. Complete PHR approval first."}
