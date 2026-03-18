import json
import os
from datetime import datetime, timedelta
from Config import DATA_FILE, CHANNELS as _DEFAULT_CHANNELS

_default = {
    "dosts":               {},
    "premium":             {},
    "cookies":             None,
    "channels":            {},
    "verified_users":      {},     # uid -> {expiry, name}
    "verification_enabled": False, # owner toggle
}

def _load():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                for key in _default:
                    if key not in data:
                        data[key] = _default[key]
                return data
        except Exception:
            pass
    return {k: (v.copy() if isinstance(v, dict) else v) for k, v in _default.items()}

def _save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)

# ─────── Dost management ───────

def add_dost(user_id: int, username: str, added_by: int):
    data = _load()
    data["dosts"][str(user_id)] = {
        "username": username,
        "added_by": added_by,
        "added_at": datetime.now().isoformat(),
    }
    _save(data)

def remove_dost(user_id: int):
    data = _load()
    removed = data["dosts"].pop(str(user_id), None)
    _save(data)
    return removed is not None

def get_dosts():
    return _load()["dosts"]

def is_dost(user_id: int):
    return str(user_id) in _load()["dosts"]

def dost_count():
    return len(_load()["dosts"])

# ─────── Premium management ───────

def add_premium(user_id: int, days: int):
    data = _load()
    existing = data["premium"].get(str(user_id))
    if existing:
        try:
            expiry = datetime.fromisoformat(existing["expiry"])
            expiry = expiry + timedelta(days=days) if expiry > datetime.now() else datetime.now() + timedelta(days=days)
        except Exception:
            expiry = datetime.now() + timedelta(days=days)
    else:
        expiry = datetime.now() + timedelta(days=days)
    data["premium"][str(user_id)] = {"expiry": expiry.isoformat()}
    _save(data)
    return expiry

def remove_premium(user_id: int):
    data = _load()
    removed = data["premium"].pop(str(user_id), None)
    _save(data)
    return removed is not None

def is_premium(user_id: int):
    data = _load()
    entry = data["premium"].get(str(user_id))
    if not entry:
        return False
    try:
        return datetime.fromisoformat(entry["expiry"]) > datetime.now()
    except Exception:
        return False

def premium_expiry(user_id: int):
    data = _load()
    entry = data["premium"].get(str(user_id))
    if not entry:
        return None
    try:
        return datetime.fromisoformat(entry["expiry"])
    except Exception:
        return None

def get_all_premium():
    return _load()["premium"]

def premium_count():
    data = _load()
    now = datetime.now()
    count = 0
    for entry in data["premium"].values():
        try:
            if datetime.fromisoformat(entry["expiry"]) > now:
                count += 1
        except Exception:
            pass
    return count

# ─────── Cookies management ───────

def set_cookies(content: str):
    data = _load()
    data["cookies"] = content
    _save(data)
    with open("cookies.txt", "w") as f:
        f.write(content)

def get_cookies():
    return _load().get("cookies")

def delete_cookies():
    data = _load()
    data["cookies"] = None
    _save(data)
    if os.path.exists("cookies.txt"):
        os.remove("cookies.txt")

# ─────── Verification management ───────

def is_verification_enabled() -> bool:
    return bool(_load().get("verification_enabled", False))

def set_verification_enabled(enabled: bool):
    data = _load()
    data["verification_enabled"] = enabled
    _save(data)

def add_verified(user_id: int, name: str, hours: int = 4):
    data = _load()
    expiry = datetime.now() + timedelta(hours=hours)
    data["verified_users"][str(user_id)] = {
        "name":   name,
        "expiry": expiry.isoformat(),
    }
    _save(data)
    return expiry

def is_verified(user_id: int) -> bool:
    data = _load()
    entry = data.get("verified_users", {}).get(str(user_id))
    if not entry:
        return False
    try:
        return datetime.fromisoformat(entry["expiry"]) > datetime.now()
    except Exception:
        return False

def remove_verified(user_id: int) -> bool:
    data = _load()
    removed = data.get("verified_users", {}).pop(str(user_id), None)
    _save(data)
    return removed is not None

def get_all_verified() -> dict:
    return _load().get("verified_users", {})

def verified_expiry(user_id: int):
    data = _load()
    entry = data.get("verified_users", {}).get(str(user_id))
    if not entry:
        return None
    try:
        return datetime.fromisoformat(entry["expiry"])
    except Exception:
        return None

# ─────── Channel management ───────

def get_all_channels():
    """Return merged dict: default channels + custom channels from storage.
    Custom channels override defaults with same key."""
    merged = {}
    for key, ch in _DEFAULT_CHANNELS.items():
        merged[key] = dict(ch, _source="default")
    custom = _load().get("channels", {})
    for key, ch in custom.items():
        merged[key] = dict(ch, _source="custom")
    return merged

def get_custom_channels():
    return _load().get("channels", {})

def add_channel(key: str, name: str, emoji: str, tplay_url: str, jiotv_url: str):
    data = _load()
    data["channels"][key.lower().strip()] = {
        "name": name,
        "emoji": emoji or "📺",
        "sources": {
            "TPlay": tplay_url,
            "JioTV": jiotv_url,
        },
    }
    _save(data)

def remove_channel(key: str):
    data = _load()
    removed = data["channels"].pop(key.lower().strip(), None)
    _save(data)
    return removed is not None

def update_channel(key: str, name: str, emoji: str, tplay_url: str, jiotv_url: str):
    data = _load()
    data["channels"][key.lower().strip()] = {
        "name": name,
        "emoji": emoji or "📺",
        "sources": {
            "TPlay": tplay_url,
            "JioTV": jiotv_url,
        },
    }
    _save(data)
