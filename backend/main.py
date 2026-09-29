"""Cliniva 10/10+ prod-track API — memory + scribe + safety + QR + FHIR + ABDM + auth + ops."""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.abdm import consent_artefact, hip_release_bundle
from backend.audit import dpdp_notice, log, read_all
from backend.auth import login as auth_login, require_role, valid_mci
from backend.audio_scribe import transcribe
from backend.config import DATA_RESIDENCY
from backend.consent import Consent, booking_suggestion, filter_memory_by_consent
from backend.fhir import fhir_bundle
from backend.ops import chain_log, memory_regression, retention_check, send_reminder, suggest_slots, verify_chain
from backend.rx_sign import sign_prescription, verify_prescription
from backend.safety import check_interactions, drug_info, find_alternatives, rules_source
from backend.scribe import apply_correction, draft_soap
from memory.hindsight_client import bank_id_for_patient, bank_summary, recall, reflect, retain

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RX_STORE = DATA / "rx_store.json"

app = FastAPI(title="Cliniva 10/10")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FRONTEND = ROOT / "frontend"
if FRONTEND.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND), html=True), name="app")


def _load_patients() -> dict:
    out = {}
    for f in sorted(DATA.glob("demo_patient*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            out[p["patient_id"]] = p
        except Exception:
            pass
    return out


def _load_rx() -> dict:
    if RX_STORE.exists():
        try:
            return json.loads(RX_STORE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_rx(store: dict):
    RX_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


class ConsultIn(BaseModel):
    patient_id: str = "demo-001"
    transcript: str
    allergies: list[str] | None = None


class CorrectIn(BaseModel):
    patient_id: str = "demo-001"
    draft: dict
    correction: str


class SignIn(BaseModel):
    patient_id: str = "demo-001"
    doctor_id: str = "dr-demo"
    doctor_reg: str = "MCI-12345"
    meds: list = ["azithromycin 500mg OD x3d"]
    soap: dict = {"assessment": "Pharyngitis", "plan": "Azithro post-correction"}


@app.get("/health")
def health():
    return {"ok": True, "service": "cliniva-10/10"}


@app.get("/patients")
def patients():
    return list(_load_patients().values())


@app.get("/consent-notice")
def consent_notice():
    return dpdp_notice()


@app.get("/audit")
def audit(limit: int = 50):
    return read_all(limit)


@app.post("/consult")
def consult(inp: ConsultIn):
    pmap = _load_patients()
    p = pmap.get(inp.patient_id, {})
    allergies = inp.allergies if inp.allergies is not None else [a["agent"] for a in p.get("allergies", [])]
    bank = bank_id_for_patient(inp.patient_id)
    mem = reflect(bank, inp.transcript)
    draft = draft_soap(inp.transcript, mem)
    safety = check_interactions(draft.get("draft_meds", []), allergies)
    log("consult", inp.patient_id, "doctor", {"verdict": safety.get("verdict"), "severity": safety.get("severity")})
    return {"bank": bank, "patient": {"patient_id": inp.patient_id, "allergies": allergies},
            "memory": mem, "draft": draft, "safety": safety}


@app.post("/correct")
def correct(inp: CorrectIn):
    bank = bank_id_for_patient(inp.patient_id)
    updated = apply_correction(inp.draft, inp.correction)
    retain(bank, inp.correction, kind="correction", metadata={"actor": "doctor"})
    pmap = _load_patients()
    p = pmap.get(inp.patient_id, {})
    allergies = [a["agent"] for a in p.get("allergies", [])] or ["penicillin"]
    safety2 = check_interactions(updated.get("draft_meds", []), allergies)
    mem = recall(bank, "followup preferences")
    booking = booking_suggestion(p.get("preferences", {"followup_days": ["Saturday"], "slot": "morning"}), mem.get("observations", []))
    summary = bank_summary(bank)
    log("correction", inp.patient_id, "doctor", {"correction": inp.correction[:200], "recheck": safety2.get("verdict")})
    return {"updated": updated, "safety_recheck": safety2, "booking": booking, "memory": mem, "learning": summary}


@app.post("/sign")
def sign(inp: SignIn):
    signed = sign_prescription(inp.patient_id, inp.doctor_id, inp.doctor_reg, inp.meds, inp.soap)
    store = _load_rx()
    store[signed["rx_id"]] = {"token": signed["token"], "body": signed["body"], "hash": signed["hash"]}
    _save_rx(store)
    log("rx_sign", inp.patient_id, inp.doctor_id, {"rx_id": signed["rx_id"], "meds": inp.meds})
    return signed


@app.post("/verify")
def verify(token: dict):
    v = verify_prescription(token.get("token", ""))
    log("rx_verify", v.get("rx", {}).get("patient_id", ""), "pharmacy", {"valid": v.get("valid")})
    return v


@app.get("/timeline/{patient_id}")
def timeline(patient_id: str, revoked: bool = False, no_allergies: bool = False, no_meds: bool = False):
    bank = bank_id_for_patient(patient_id)
    mem = recall(bank, "patient history allergies meds")
    pmap = _load_patients()
    p = pmap.get(patient_id, {})
    c = Consent(revoked=revoked, allergies=not no_allergies, medications=not no_meds)
    base = {"facts": mem.get("facts", []), "observations": mem.get("observations", []),
            "mental_models": mem.get("mental_models", []),
            "allergies": [a["agent"] for a in p.get("allergies", [])],
            "patient": {k: p.get(k) for k in ("patient_id", "name", "age", "conditions", "current_meds", "preferences")}}
    log("timeline_access", patient_id, "doctor", {"revoked": revoked})
    return filter_memory_by_consent(base, c)


@app.get("/memory/{patient_id}")
def memory_view(patient_id: str):
    return bank_summary(bank_id_for_patient(patient_id))


@app.post("/alternatives")
def alternatives(d: dict):
    return {"drug": d.get("drug", ""), "alternatives": find_alternatives(d.get("drug", ""))}


@app.post("/drug-info")
def drug_info_ep(d: dict):
    return drug_info(d.get("drug", ""))


@app.get("/rx/{rx_id}")
def get_rx(rx_id: str):
    store = _load_rx()
    if rx_id not in store:
        return {"found": False}
    return {"found": True, "stored": store[rx_id], "verification": verify_prescription(store[rx_id]["token"])}


@app.get("/fhir-rx/{rx_id}")
def fhir_rx(rx_id: str):
    store = _load_rx()
    rec = store.get(rx_id)
    if not rec:
        return {"found": False}
    v = verify_prescription(rec["token"])
    if not v.get("valid"):
        return {"found": True, "valid": False}
    rx = v["rx"]
    pmap = _load_patients()
    p = pmap.get(rx.get("patient_id"), {})
    bundle = fhir_bundle(rx.get("patient_id"), p.get("abha_id", ""), rx.get("doctor_id"), rx.get("doctor_reg"), rx.get("meds", []), rx_id, rx.get("issued_at", 0))
    return {"found": True, "valid": True, "fhir_bundle": bundle}


@app.post("/tamper-demo")
def tamper_demo(d: dict):
    """Flip one char of a valid token to prove verification catches tampering."""
    tok = d.get("token", "")
    if not tok:
        return {"error": "no token"}
    bad = tok[:-1] + ("a" if tok[-1] != "a" else "b")
    return {"original": verify_prescription(tok), "tampered": verify_prescription(bad)}


@app.get("/verify-page/{rx_id}", response_class=HTMLResponse)
def verify_page(rx_id: str):
    store = _load_rx()
    rec = store.get(rx_id)
    if not rec:
        return f"<h2>Rx {rx_id} not found</h2>"
    v = verify_prescription(rec["token"])
    status = "VALID - verified" if v.get("valid") else "TAMPERED - rejected"
    rx = v.get("rx", {})
    return f"""<html><body style="font-family:sans-serif;max-width:680px;margin:40px auto">
    <h2>Cliniva e-Prescription: {status}</h2>
    <p><b>Rx:</b> {rx_id} | <b>Patient:</b> {rx.get('patient_id')} | <b>Doctor:</b> {rx.get('doctor_id')} ({rx.get('doctor_reg')})</p>
    <p><b>Meds:</b> {', '.join(rx.get('meds', []))}</p>
    <p><b>Hash:</b> <code>{v.get('hash')}</code></p>
    <p><a href="/fhir-rx/{rx_id}">Download FHIR R4 bundle (ABDM)</a></p>
    <p style="color:#666">PCI format / FHIR PrescriptionRecord demo. Supports, does not replace clinical judgment.</p>
    </body></html>"""


@app.get("/", response_class=HTMLResponse)
def root():
    return '<html><body style="font-family:sans-serif;margin:40px"><h2>Cliniva 10/10 API running</h2><p>Open <a href="/app/">/app/</a> for the demo frontend.</p></body></html>'


# ---- prod-track: rate-limit (in-memory), auth, ABDM, audio, ops ----
_HITS: dict = {}


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    if request.url.path in ("/consult", "/sign"):
        ip = request.client.host if request.client else "local"
        now = time.time()
        bucket = _HITS.setdefault(ip, [])
        while bucket and now - bucket[0] > 60:
            bucket.pop(0)
        if len(bucket) >= 60:
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "rate limited (60/min). Retry later."}, status_code=429)
        bucket.append(now)
    return await call_next(request)


@app.get("/ops/health")
def ops_health():
    return {"ok": True, "residency": DATA_RESIDENCY, "rules": rules_source(), "chain": verify_chain(50), "eval": memory_regression()}


@app.post("/auth/login")
def auth_login_ep(d: dict):
    return auth_login(d.get("username", ""), d.get("password", ""))


@app.post("/auth/check-mci")
def check_mci(d: dict):
    return {"reg": d.get("reg", ""), "valid_format": valid_mci(d.get("reg", ""))}


@app.post("/abdm/consent")
def abdm_consent(d: dict):
    art = consent_artefact(d.get("abha", "91-1234-5678-9012"), d.get("hiu", "cliniva-hiu"), d.get("hip", "demo-clinic"), d.get("purpose", "OPD consultation"), d.get("records", ["Prescription", "OPConsult"]))
    chain_log("abdm_consent", d.get("patient_id", ""), "system", {"artefact": art["artefact_id"]})
    return art


@app.post("/audio/transcribe")
def audio_transcribe(d: dict):
    return transcribe(d.get("hint", "throat"), d.get("hint", "throat"), d.get("mic_consent", False))


@app.post("/booking/slots")
def booking_slots(d: dict):
    pmap = _load_patients()
    prefs = pmap.get(d.get("patient_id", "demo-001"), {}).get("preferences", {})
    return suggest_slots(prefs, d.get("booked", []))


@app.post("/booking/remind")
def booking_remind(d: dict):
    return send_reminder(d.get("channel", "sms"), d.get("to", "+91-00000"), d.get("text", "Follow-up reminder"))


@app.get("/ops/retention/{rtype}")
def retention_ep(rtype: str):
    return retention_check(rtype, int(time.time()) - 365 * 24 * 3600)


@app.get("/ops/chain")
def chain_ep():
    return verify_chain(200)
