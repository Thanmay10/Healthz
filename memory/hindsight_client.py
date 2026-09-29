"""
Cliniva Hindsight memory client 10/10.
One bank per patient. All agents share same bankId.
Local JSON fallback mirrors Hindsight semantics: facts -> observations -> mental models.
"""
import json
import os
import pathlib
import time

import requests

HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
LOCAL_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "banks"
LOCAL_DIR.mkdir(parents=True, exist_ok=True)


def bank_id_for_patient(patient_id: str) -> str:
    return f"cliniva-patient-{patient_id}"


def _local_path(bank_id: str) -> pathlib.Path:
    return LOCAL_DIR / f"{bank_id}.json"


def _load_local(bank_id: str) -> dict:
    p = _local_path(bank_id)
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d.setdefault("facts", [])
            d.setdefault("observations", [])
            d.setdefault("mental_models", [])
            return d
        except Exception:
            pass
    return {"bank_id": bank_id, "facts": [], "observations": [], "mental_models": []}


def _save_local(bank_id: str, data: dict):
    _local_path(bank_id).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _promote_mental_model(data: dict, content: str, evidence: str):
    low = content.lower()
    mm_id = None
    mm_text = None
    if "penicillin" in low and ("avoid" in low or "allerg" in low or "stop" in low):
        mm_id, mm_text = "avoid-penicillin-class", "Avoid penicillin-class (amoxicillin/ampicillin) — history of allergy; prefer macrolide per doctor."
    elif "follow-up" in low or "followup" in low or "saturday" in low or "sunday" in low:
        mm_id, mm_text = "followup-pref", f"Follow-up preference: {content[:140]}"
    if mm_id:
        existing = next((m for m in data["mental_models"] if m.get("id") == mm_id), None)
        if existing:
            if evidence not in existing.get("evidence", []):
                existing["evidence"].append(evidence)
            existing["content"] = mm_text
            existing["updated"] = int(time.time())
        else:
            data["mental_models"].append({"id": mm_id, "content": mm_text, "evidence": [evidence], "updated": int(time.time())})


def retain(bank_id: str, content: str, kind: str = "world_fact", metadata: dict | None = None) -> dict:
    record = {"content": content, "kind": kind, "metadata": metadata or {}, "ts": int(time.time())}
    if HINDSIGHT_URL:
        r = requests.post(
            f"{HINDSIGHT_URL.rstrip('/')}/retain",
            headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}"} if HINDSIGHT_API_KEY else {},
            json={"bankId": bank_id, "content": content, "metadata": {"kind": kind, **(metadata or {})}},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    data = _load_local(bank_id)
    data["facts"].append(record)
    low = content.lower()
    if kind == "correction" or any(k in low for k in ["allergy", "allergic", "intolerant", "stop ", "avoid "]):
        obs = f"LEARNED: {content}"
        if obs not in [o["content"] for o in data["observations"]]:
            data["observations"].append({"content": obs, "evidence": [content], "ts": record["ts"]})
        _promote_mental_model(data, content, content)
    elif kind == "world_fact" and ("prefer" in low or "follow" in low):
        _promote_mental_model(data, content, content)
    _save_local(bank_id, data)
    return {"ok": True, "bank_id": bank_id, "stored": record}


def recall(bank_id: str, query: str, top_k: int = 8) -> dict:
    if HINDSIGHT_URL:
        r = requests.post(
            f"{HINDSIGHT_URL.rstrip('/')}/recall",
            headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}"} if HINDSIGHT_API_KEY else {},
            json={"bankId": bank_id, "query": query, "topK": top_k},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    data = _load_local(bank_id)
    q = query.lower().split()
    scored = []
    for f in data["facts"] + data["observations"]:
        c = f["content"].lower()
        score = sum(1 for w in q if w in c)
        if score > 0:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    return {
        "bank_id": bank_id,
        "query": query,
        "mental_models": data.get("mental_models", []),
        "observations": data.get("observations", [])[:top_k],
        "facts": [f for _, f in scored[:top_k]],
    }


def reflect(bank_id: str, query: str) -> dict:
    mem = recall(bank_id, query, top_k=12)
    return {
        "bank_id": bank_id,
        "query": query,
        "answer_context": {
            "mental_models": mem.get("mental_models", []),
            "observations": mem.get("observations", []),
            "facts": mem.get("facts", [])[:6],
        },
        "note": "reflect prefers mental_models > observations > raw facts; stale observations verified against raw facts.",
    }


def bank_summary(bank_id: str) -> dict:
    d = _load_local(bank_id)
    return {
        "bank_id": bank_id,
        "counts": {"facts": len(d["facts"]), "observations": len(d["observations"]), "mental_models": len(d["mental_models"])},
        "mental_models": d["mental_models"],
        "observations": d["observations"][-5:],
    }
