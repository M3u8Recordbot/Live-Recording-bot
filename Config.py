import os

# Bot token from @botfather
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8619959255:AAHq2ekj90Mwx2cI6IdNd-b16JC86YTDMlM")

# From my.telegram.org/
API_ID = int(os.environ.get("API_ID", "29481626"))
API_HASH = os.environ.get("API_HASH", "4892185769903521077c4cea97808b8c")

# Owner IDs (full access, no restrictions)
OWNER_IDS = [969084369, 5856009289]

# Auth users (trusted, no verification needed)
AUTH_USERS = [969084369, 2800583882, 5856009289, 1900583882]

# Pre-configured Dosts (added on startup if not already in storage)
DEFAULT_DOSTS = {
    1900583882: "Dost",
}

# Bot branding
BOT_USERNAME = "M3u8LiveRecordingBot"
CHANNEL_TAG  = "LittleSinghamChannel"
WATERMARK    = "Anime-Cartoon.kesug.com"
GROUP_LINK   = "https://t.me/+m_yCHi8Bdv02Y2Y1"

# Free user limits
FREE_MAX_DURATION_HOURS = 6
FREE_MAX_CONCURRENT     = 5
FREE_MAX_GROUP_LINKS    = 50

# Premium plans (days → price USD)
PREMIUM_PLANS = {"7": 25, "15": 50, "30": 75}

# Session name
SESSION_NAME = "RipperBot"

# Storage file
DATA_FILE    = "data.json"
COOKIES_FILE = "cookies.txt"

# Admin panel password
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ─── Verification system ───
SHORTENER_API    = os.environ.get("SHORTENER_API", "65aa5be4d757fb7242fff9dde00f6cd5d4acc977")
SHORTENER_DOMAIN = "shortxlinks.in"
VERIFY_HOURS     = 4                              # hours access granted after verification
VERIFY_GROUP     = "https://t.me/c/2314084106/2130"   # how-to group link
BOT_LINK         = f"https://telegram.me/M3u8LiveRecordingBot"

# ─── Predefined channels ───
# Keys are lowercase search aliases, value has display name + sources
CHANNELS = {
    "pogo": {
        "name": "Pogo",
        "emoji": "📺",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0dh/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/559.m3u8",
        },
    },
    "sony yay": {
        "name": "Sony Yay",
        "emoji": "📺",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0cl/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/872.m3u8",
        },
    },
    "cartoon network": {
        "name": "Cartoon Network",
        "emoji": "🎨",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0cn/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/166.m3u8",
        },
    },
    "cn": {
        "name": "Cartoon Network",
        "emoji": "🎨",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0cn/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/166.m3u8",
        },
    },
    "discovery kids": {
        "name": "Discovery Kids",
        "emoji": "🔭",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0dg/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/554.m3u8",
        },
    },
    "nick": {
        "name": "Nick",
        "emoji": "🟠",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0cq/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/545.m3u8",
        },
    },
    "nickelodeon": {
        "name": "Nick",
        "emoji": "🟠",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0cq/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/545.m3u8",
        },
    },
    "nick jr": {
        "name": "Nick Jr",
        "emoji": "🟡",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0di/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/544.m3u8",
        },
    },
    "sonic": {
        "name": "Sonic",
        "emoji": "💙",
        "sources": {
            "TPlay":  "http://103.229.254.25:7001/play/a0dl/index.m3u8",
            "JioTV":  "http://103.180.212.191:3500/live/815.m3u8",
        },
    },
}

def resolve_channel(name: str):
    """Return channel dict if name matches a predefined channel, else None."""
    key = name.strip().lower()
    return CHANNELS.get(key)
