import re
import time
import threading
import urllib.request
import json
import os

_SETTINGS_FILE   = "playlist_settings.json"
_DEFAULT_URL     = "https://netx.streamstar18.workers.dev/zio1"

def _load_url() -> str:
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE) as f:
                return json.load(f).get("url", _DEFAULT_URL)
    except Exception:
        pass
    return _DEFAULT_URL

def _save_url(url: str):
    try:
        with open(_SETTINGS_FILE, "w") as f:
            json.dump({"url": url}, f)
    except Exception:
        pass

PLAYLIST_URL = _load_url()
CACHE_TTL    = 3600   # refresh every hour

# ── In-memory cache ──────────────────────────
_cache:      list  = []     # list of {idx, name, group, url}
_cache_ts:   float = 0.0
_cache_lock  = threading.Lock()

def update_url(new_url: str):
    """Update playlist URL, persist it, and flush the cache."""
    global PLAYLIST_URL, _cache, _cache_ts
    PLAYLIST_URL = new_url.strip()
    _save_url(PLAYLIST_URL)
    with _cache_lock:
        _cache    = []
        _cache_ts = 0.0

def get_current_url() -> str:
    return PLAYLIST_URL

def clear_cache():
    """Force re-fetch on next get_channels() call."""
    global _cache, _cache_ts
    with _cache_lock:
        _cache    = []
        _cache_ts = 0.0

# ── Category keyword maps ─────────────────────
SPORTS_GROUPS = {"FC BD", "FC IN", "CRICHD", "BALL FTP", "AKKAS GO", "REAL IP1", "REAL IP2"}
SPORTS_KEYWORDS = ["sport", "cricket", "football", "soccer", "ipl", "t20", "match",
                   "live score", "copa", "league", "champions", "vs ", "wc ", "premier"]
KIDS_KEYWORDS   = ["kid", "cartoon", "nick", "pogo", "disney", "junior", "jr",
                   "toon", "cbeebies", "baby", "junior", "zing", "hungama",
                   "discovery kids", "sony yay", "motu", "peppa", "dora"]
MOVIES_GROUPS   = {"MOVIES"}
MOVIES_KEYWORDS = ["movie", "cinema", "film", "films", "pictures", "cinemax",
                   "hbo", "star gold", "zee cinema", "sony max", "b4u movie"]

def _classify(name: str, group: str) -> str:
    nl = name.lower()
    gl = group.lower()
    if group in MOVIES_GROUPS or any(k in nl or k in gl for k in MOVIES_KEYWORDS):
        return "Movies"
    if group in SPORTS_GROUPS or any(k in nl or k in gl for k in SPORTS_KEYWORDS):
        return "Sports"
    if any(k in nl or k in gl for k in KIDS_KEYWORDS):
        return "Kids"
    return "All"

def _fetch_and_parse() -> list:
    try:
        req  = urllib.request.Request(PLAYLIST_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=20)
        raw  = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[Playlist] Fetch error: {e}")
        return []

    channels = []
    lines    = raw.splitlines()
    idx      = 0
    i        = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # parse name from the comma-separated part
            name_match = re.search(r',(.+)$', line)
            name       = name_match.group(1).strip() if name_match else "Unknown"
            # parse group-title
            grp_match  = re.search(r'group-title="([^"]*)"', line)
            group      = grp_match.group(1).strip() if grp_match else ""
            # skip EXTVLCOPT / EXTHTTP helper lines
            j = i + 1
            while j < len(lines) and (lines[j].startswith("#") or not lines[j].strip()):
                j += 1
            if j < len(lines):
                url = lines[j].strip()
                if url and not url.startswith("#"):
                    cat = _classify(name, group)
                    channels.append({
                        "idx":   idx,
                        "name":  name,
                        "group": group,
                        "url":   url,
                        "cat":   cat,
                    })
                    idx += 1
                    i = j + 1
                    continue
        i += 1
    return channels

def get_channels(force: bool = False) -> list:
    global _cache, _cache_ts
    with _cache_lock:
        if force or not _cache or (time.time() - _cache_ts) > CACHE_TTL:
            result = _fetch_and_parse()
            if result:
                _cache    = result
                _cache_ts = time.time()
        return list(_cache)

def get_by_idx(idx: int) -> dict | None:
    channels = get_channels()
    if 0 <= idx < len(channels):
        return channels[idx]
    return None

def filter_channels(channels: list, category: str, query: str = "") -> list:
    q = query.strip().lower()
    result = []
    for ch in channels:
        if category != "All" and ch["cat"] != category:
            continue
        if q and q not in ch["name"].lower() and q not in ch["group"].lower():
            continue
        result.append(ch)
    return result

def search_channels(query: str) -> list:
    channels = get_channels()
    q = query.strip().lower()
    if not q:
        return []
    return [ch for ch in channels if q in ch["name"].lower() or q in ch["group"].lower()]

# Pre-load in background on import
def _preload():
    get_channels()

threading.Thread(target=_preload, daemon=True).start()
