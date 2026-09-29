"""Hash-chained audit (tamper-evident) + retention policies + booking engine + eval."""
import hashlib
import json
import pathlib
import time

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
CHAIN = DATA / "audit_chain.jsonl"

RETENTION = {
    "opd_note": {"years": 10, "basis": "MCI/Clinical Establishments record rules"},
    "prescription": {"years": 10, "basis": "Pharmacy Practice Regulations"},
    "audio": {"years": 3, "basis": "configurable; erase on request after minimum"},
    "analytics": {"years": 1, "basis": "DPDP purpose limitation; erase on withdraw"},
}


def chain_log(event: str, patient_id: str = "", actor: str = "", detail: dict | None = None) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    prev = "GENESIS"
    if CHAIN.exists():
        try:
            last = CHAIN.read_text(encoding="utf-8").strip().split("\n")[-1]
            prev = json.loads(last).get("hash", prev)
        except Exception:
            pass
    rec = {"ts": int(time.time()), "event": event, "patient_id": patient_id, "actor": actor, "detail": detail or {}, "prev": prev}
    rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
    with CHAIN.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def verify_chain(limit: int = 200) -> dict:
    if not CHAIN.exists():
        return {"ok": True, "checked": 0}
    lines = CHAIN.read_text(encoding="utf-8").strip().split("\n")[-limit:]
    prev = None
    for i, ln in enumerate(lines):
        r = json.loads(ln)
        h = r.pop("hash")
        if hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest() != h:
            return {"ok": False, "bad_index": i}
        if prev is not None and r.get("prev") != prev:
            return {"ok": False, "bad_link": i}
        prev = h
    return {"ok": True, "checked": len(lines)}


def retention_check(record_type: str, created_ts: int) -> dict:
    pol = RETENTION.get(record_type, {"years": 3, "basis": "default"})
    due = created_ts + pol["years"] * 365 * 24 * 3600
    return {"type": record_type, "keep_until": due, "expired": int(time.time()) > due, "basis": pol["basis"]}


SLOTS = ["Sat 10:00", "Sat 11:00", "Sun 18:00", "Mon 09:30"]


def suggest_slots(preferences: dict, booked: list | None = None) -> dict:
    booked = booked or []
    pref_days = preferences.get("followup_days", [])
    ranked = sorted(SLOTS, key=lambda s: 0 if any(d[:3].lower() in s.lower() for d in pref_days) else 1)
    free = [s for s in ranked if s not in booked]
    return {"suggested": free[:3], "channel": preferences.get("channel", "sms"), "reminder": "T-24h + T-2h"}


def send_reminder(channel: str, to: str, text: str) -> dict:
    # mock provider; swap with Twilio/WhatsApp in prod via SMS_PROVIDER
    return {"sent": True, "channel": channel, "to": to, "preview": text[:120], "provider": "mock (set SMS_PROVIDER=twilio in prod)"}


def memory_regression() -> dict:
    """Tiny LongMemEval-style check: correction must be recallable."""
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from memory.hindsight_client import bank_id_for_patient, recall, retain
    b = bank_id_for_patient("eval-probe")
    retain(b, "Probe allergy: test-penicillin avoid", kind="correction", metadata={"eval": True})
    hit = any("test-penicillin" in f.get("content", "").lower() for f in recall(b, "test-penicillin allergy")["facts"])
    stale = recall(b, "followup")  # exercises path
    return {"recall_hit": hit, "recall_path_ok": "facts" in stale}
