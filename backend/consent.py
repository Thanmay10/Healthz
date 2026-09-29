"""Consent-gated access. DPDP + ABDM HIE-CM aligned (demo)."""
from dataclasses import dataclass

@dataclass
class Consent:
    history: bool = True
    allergies: bool = True
    medications: bool = True
    purpose: str = "OPD consultation"
    revoked: bool = False

    def can_access(self, scope: str) -> bool:
        if self.revoked:
            return False
        return bool(getattr(self, scope, False))

    def revoke(self):
        self.revoked = True

    def grant(self):
        self.revoked = False

def filter_memory_by_consent(memory: dict, consent: Consent) -> dict:
    """Strip scopes without consent before showing timeline to doctor."""
    out = dict(memory)
    if not consent.can_access("allergies"):
        out["allergies"] = []
        out["observations"] = [o for o in out.get("observations", []) if "allerg" not in o.get("content", "").lower()]
    if not consent.can_access("medications"):
        out["facts"] = [f for f in out.get("facts", []) if "amox" not in f.get("content", "").lower()]
    if consent.revoked:
        out["locked"] = True
        out["lock_reason"] = "Consent revoked — timeline locked per DPDP. Re-consent required."
    return out

def booking_suggestion(preferences: dict, memory_obs: list) -> dict:
    day = (preferences.get("followup_days") or ["Saturday"])[0]
    slot = preferences.get("slot", "morning")
    lang = preferences.get("language", "en")
    extra = ""
    if any("missed" in (o.get("content", "").lower()) for o in memory_obs):
        extra = " (priority: missed last follow-up)"
    return {"suggested": f"{day} {slot}{extra}", "channel": preferences.get("channel", "sms"), "language": lang}
