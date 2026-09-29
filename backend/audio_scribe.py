"""Audio scribe: Whisper when available, deterministic stub otherwise. Mic consent required."""
import pathlib

TRANSCRIPTS = {
    "throat": "Doctor: What brings you today? Patient: I have fever and throat pain since 2 days. Doctor: Any drug allergies? Patient: Yes, penicillin gave me rash last year.",
    "bp": "Doctor: BP check today? Patient: Yes, mild headache. No known drug allergies.",
}


def transcribe(audio_path: str = "", hint: str = "throat", mic_consent: bool = False) -> dict:
    if not mic_consent:
        return {"ok": False, "reason": "Mic consent required before recording (DPDP). Show consent checkbox first."}
    try:
        import faster_whisper  # type: ignore
        return {"ok": True, "engine": "faster-whisper", "note": "wire model load here in prod", "hint": hint}
    except Exception:
        key = "bp" if "bp" in (hint or "").lower() or "headache" in (hint or "").lower() else "throat"
        return {"ok": True, "engine": "stub-demo", "transcript": TRANSCRIPTS[key],
                "note": "Stub for offline demo. Install faster-whisper + ffmpeg for real audio."}


def save_upload(data: bytes, name: str = "consult.webm") -> str:
    p = pathlib.Path(__file__).resolve().parent.parent / "data" / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    f = p / name
    f.write_bytes(data)
    return str(f)
