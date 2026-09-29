"""Auth/RBAC demo: MCI format check + hashed passwords + JWT roles. Swap with Keycloak/ABDM HPR in prod."""
import hashlib
import re
import time
import jwt

SECRET = "cliniva-auth-demo-change-in-prod"
MCI_RE = re.compile(r"^(MCI|KMC|TNMC|MMC)-[A-Z0-9-]{4,20}$", re.I)

USERS = {
    "dr-demo": {"pw_hash": hashlib.sha256(b"demo123").hexdigest(), "role": "doctor", "reg": "MCI-12345"},
    "pharm-demo": {"pw_hash": hashlib.sha256(b"demo123").hexdigest(), "role": "pharmacist", "reg": "PCI-999"},
}


def valid_mci(reg: str) -> bool:
    return bool(MCI_RE.match((reg or "").strip()))


def login(username: str, password: str) -> dict:
    u = USERS.get(username)
    if not u or u["pw_hash"] != hashlib.sha256(password.encode()).hexdigest():
        return {"ok": False, "reason": "bad credentials"}
    tok = jwt.encode({"sub": username, "role": u["role"], "exp": int(time.time()) + 8 * 3600}, SECRET, algorithm="HS256")
    return {"ok": True, "token": tok, "role": u["role"]}


def require_role(token: str, roles: list) -> dict:
    try:
        d = jwt.decode(token, SECRET, algorithms=["HS256"])
    except Exception as e:
        return {"ok": False, "reason": str(e)}
    if d.get("role") not in roles:
        return {"ok": False, "reason": f"role {d.get('role')} not in {roles}"}
    return {"ok": True, "user": d}
