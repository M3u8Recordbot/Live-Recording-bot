import asyncio
import os
import re
import time
import threading
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from Config import (
    API_ID, API_HASH, BOT_TOKEN, OWNER_IDS, AUTH_USERS,
    SESSION_NAME, CHANNEL_TAG, WATERMARK, GROUP_LINK,
    FREE_MAX_DURATION_HOURS, FREE_MAX_CONCURRENT,
    FREE_MAX_GROUP_LINKS, PREMIUM_PLANS,
    CHANNELS, DEFAULT_DOSTS,
    SHORTENER_API, SHORTENER_DOMAIN, VERIFY_HOURS, VERIFY_GROUP, BOT_LINK,
)
import storage
import playlist_mgr
from web import run_flask

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────

MAX_RECORDINGS   = 4      # max concurrent recordings per user
BLOCK_DURATION   = 3600   # seconds blocked after 3 warnings (1 hour)
PL_PAGE_SIZE     = 15     # channels per page in /PlaylistChannels

# ─────────────────────────────────────────────
#  In-memory state
# ─────────────────────────────────────────────

pending:          dict = {}   # uid -> setup dict (pre-start choices)
active:           dict = {}   # uid -> list of recording dicts
user_warnings:    dict = {}   # uid -> int (spam warning count)
blocked_users:    dict = {}   # uid -> unix timestamp when block expires
awaiting_cookies:   dict = {}   # uid -> True
awaiting_dost:      dict = {}   # uid -> True
awaiting_compress:  dict = {}   # uid -> True
awaiting_pl_dur:    dict = {}   # uid -> {channel dict} (waiting for duration for playlist channel)

# Source selection for /Channels flow: uid -> {"channel_key": str, "duration_str": str, "chat_id": int}
channel_pending:  dict = {}

# Verification tokens: token_str -> {"uid": int, "created": float}
verify_tokens:    dict = {}

app = Client(
    SESSION_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ─────────────────────────────────────────────
#  Startup: ensure DEFAULT_DOSTS are in storage
# ─────────────────────────────────────────────

def init_defaults():
    for uid, name in DEFAULT_DOSTS.items():
        if not storage.is_dost(uid):
            storage.add_dost(uid, name, OWNER_IDS[0])

init_defaults()

# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def is_owner(uid: int) -> bool:
    return uid in OWNER_IDS

def is_blocked(uid: int) -> bool:
    if uid in blocked_users:
        if time.time() > blocked_users[uid]:
            del blocked_users[uid]
            user_warnings[uid] = 0
            return False
        return True
    return False

def needs_verification(uid: int) -> bool:
    """Returns True if verification is enabled and user is not exempt and not verified."""
    if uid in AUTH_USERS or storage.is_dost(uid) or storage.is_premium(uid):
        return False
    # Owner: exempt only if verification is OFF, or they've added themselves via /Owner_verify
    if is_owner(uid):
        if not storage.is_verification_enabled():
            return False
        return not storage.is_verified(uid)
    return storage.is_verification_enabled() and not storage.is_verified(uid)

import secrets, urllib.request, urllib.parse, json as _json

def create_short_link(long_url: str) -> str:
    """Shorten a URL via shortxlinks.in API. Returns short URL or original on failure."""
    try:
        api_url = (
            f"https://{SHORTENER_DOMAIN}/api"
            f"?api={SHORTENER_API}"
            f"&url={urllib.parse.quote(long_url, safe='')}"
        )
        req  = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = _json.loads(resp.read().decode())
        return data.get("shortenedUrl") or data.get("short_url") or data.get("shortlink") or long_url
    except Exception:
        return long_url

def generate_verify_token(uid: int) -> str:
    token = secrets.token_urlsafe(12)
    key   = f"ST{token}"
    # clean old tokens for this uid
    for k in list(verify_tokens.keys()):
        if verify_tokens[k]["uid"] == uid:
            del verify_tokens[k]
    verify_tokens[key] = {"uid": uid, "created": time.time()}
    return key

async def send_verification_message(message: Message, uid: int):
    name  = message.from_user.first_name or "User"
    token = generate_verify_token(uid)
    deep_link   = f"{BOT_LINK}?start=verify_{token}"
    short_link  = await asyncio.get_event_loop().run_in_executor(None, create_short_link, deep_link)
    text = (
        f"🔐 **Verification Required**\n\n"
        f"Click below to unlock access for **{VERIFY_HOURS} hours**."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Verify Now", url=short_link)],
        [InlineKeyboardButton("📘 How to Verify", url=VERIFY_GROUP)],
    ])
    await message.reply(text, reply_markup=keyboard)

def active_count(uid: int) -> int:
    return len(active.get(uid, []))

def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def parse_duration(s: str) -> int:
    parts = s.strip().split(":")
    p = [int(x) for x in parts]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    elif len(p) == 2:
        return p[0] * 60 + p[1]
    return int(p[0])

def quality_to_height(quality: str) -> str:
    return {"360p": "360", "480p": "480", "720p": "720", "1080p": "1080", "Best": "best"}.get(quality, "720")

def build_output_filename(quality: str, audio_tracks: list) -> str:
    now = datetime.now()
    date_str = now.strftime("%d-%m-%Y")
    time_str = now.strftime("%I:%M:%S %p")
    height   = quality_to_height(quality)
    res_str  = "BestQ" if quality == "Best" else f"{height}p"
    if not audio_tracks or "All Tracks" in audio_tracks:
        lang = "MultiAudio"
    else:
        lang = ".".join(audio_tracks)
    return f"{CHANNEL_TAG}.[{date_str}].[{time_str}].{res_str}.[{lang}].MP32.0.128K.H264.mp4"

def build_vf_filter(quality: str, aspect: str) -> str:
    if aspect == "1536×864":
        return "scale=1536:864:force_original_aspect_ratio=decrease,pad=1536:864:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    if quality == "Best":
        if aspect == "Black Bars":
            return "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        return ""
    h = quality_to_height(quality)
    if aspect == "Original":
        return f"scale=-2:{h}"
    elif aspect == "16:9":
        return f"scale={int(int(h)*16//9)*2}:{h},setsar=1"
    elif aspect == "Black Bars":
        tw = (int(h) * 16 // 9) // 2 * 2
        return f"scale={tw}:{h}:force_original_aspect_ratio=decrease,pad={tw}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    return f"scale=-2:{h}"

def parse_ffmpeg_progress(buf: str) -> dict:
    info = {}
    for key in ["frame", "fps", "bitrate", "total_size", "out_time", "speed", "progress"]:
        m = re.search(rf"{key}=(.+)", buf)
        if m:
            info[key] = m.group(1).strip()
    return info

def cancel_recording(uid: int, rec: dict):
    proc = rec.get("proc")
    task = rec.get("task")
    if proc:
        try:
            proc.kill()
        except Exception:
            pass
    if task:
        task.cancel()

# ─────────────────────────────────────────────
#  Keyboard builders
# ─────────────────────────────────────────────

def build_record_keyboard(uid: int) -> InlineKeyboardMarkup:
    s         = pending.get(uid, {})
    quality   = s.get("quality", "720p")
    aspect    = s.get("aspect",  "Original")
    sel_audio = s.get("audio",   [])

    def q_btn(label):
        mark = "✅ " if quality == label else ""
        return InlineKeyboardButton(f"{mark}{label}", callback_data=f"q_{label}")

    def a_btn(label):
        mark = "✅ " if label in sel_audio else ""
        return InlineKeyboardButton(f"{mark}{label}", callback_data=f"a_{label}")

    AR_LABELS = {
        "1536×864":   "1536 × 864",
        "Original":   "Original Keep Source",
        "16:9":       "16:9 Widescreen",
        "Black Bars": "Black Bars Letterbox 16:9",
    }

    def ar_btn(key):
        mark  = "✅ " if aspect == key else ""
        label = AR_LABELS.get(key, key)
        return InlineKeyboardButton(f"{mark}{label}", callback_data=f"ar_{key}")

    return InlineKeyboardMarkup([
        [q_btn("360p"), q_btn("480p"), q_btn("720p"), q_btn("1080p"), q_btn("Best")],
        [InlineKeyboardButton("— ASPECT RATIO —", callback_data="noop")],
        [ar_btn("1536×864")],
        [ar_btn("Original")],
        [ar_btn("16:9")],
        [ar_btn("Black Bars")],
        [InlineKeyboardButton("— AUDIO TRACKS —", callback_data="noop")],
        [a_btn("Telugu"), a_btn("Hindi"), a_btn("Tamil"), a_btn("Malayalam")],
        [a_btn("Kannada"), a_btn("Bengali"), a_btn("Marathi"), a_btn("Odia")],
        [a_btn("English"), a_btn("All Tracks")],
        [InlineKeyboardButton("⚡ START RECORDING ⚡", callback_data="start_record")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")],
    ])

def build_playlist_keyboard(category: str, page: int, channels: list) -> InlineKeyboardMarkup:
    """Build paginated playlist keyboard with category tabs and channel buttons."""
    total  = len(channels)
    pages  = max(1, (total + PL_PAGE_SIZE - 1) // PL_PAGE_SIZE)
    page   = max(0, min(page, pages - 1))
    start  = page * PL_PAGE_SIZE
    chunk  = channels[start: start + PL_PAGE_SIZE]

    CATS = ["All", "Kids", "Movies", "Sports"]
    cat_row = [
        InlineKeyboardButton(
            f"{'▶ ' if cat == category else ''}{cat}",
            callback_data=f"pl_c_{cat}_0"
        )
        for cat in CATS
    ]

    ch_rows = []
    for ch in chunk:
        label = f"📺 {ch['name']}"
        if len(label) > 40:
            label = label[:39] + "…"
        ch_rows.append([InlineKeyboardButton(label, callback_data=f"pl_i_{ch['idx']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"pl_c_{category}_{page - 1}"))
    nav.append(InlineKeyboardButton(f"📄 {page + 1}/{pages}", callback_data="noop"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"pl_c_{category}_{page + 1}"))

    rows = [cat_row] + ch_rows + [nav]
    rows.append([InlineKeyboardButton("❌ Close", callback_data="pl_close")])
    return InlineKeyboardMarkup(rows)

def build_channels_keyboard() -> InlineKeyboardMarkup:
    """One button per unique channel name (default + custom)."""
    seen  = {}
    rows  = []
    for key, ch in storage.get_all_channels().items():
        name = ch["name"]
        if name not in seen:
            seen[name] = key
            rows.append([InlineKeyboardButton(
                f"{ch['emoji']} {name}",
                callback_data=f"ch_{key}"
            )])
    return InlineKeyboardMarkup(rows)

def build_source_keyboard(channel_key: str) -> InlineKeyboardMarkup:
    ch = storage.get_all_channels().get(channel_key, {})
    sources = ch.get("sources", {})
    btns = [
        [InlineKeyboardButton(f"📡 {src}", callback_data=f"src_{channel_key}_{src}")]
        for src in sources
    ]
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="channels_back")])
    return InlineKeyboardMarkup(btns)

# ─────────────────────────────────────────────
#  FFmpeg runner
# ─────────────────────────────────────────────

async def run_ffmpeg_record(
    client: Client, uid: int, rec: dict,
    link: str, duration_sec: int, output_file: str,
    quality: str, aspect: str, audio_tracks: list,
):
    status_msg: Message = rec["status_msg"]
    vf = build_vf_filter(quality, aspect)

    cmd = [
    "ffmpeg",
    "-y",
    "-user_agent", "Mozilla/5.0",
    "-protocol_whitelist", "file,http,https,tcp,tls",
    "-headers", "Referer: https://ranapk.online",
    "-i", link
]

if duration_sec > 0:
    cmd += ["-t", str(duration_sec)]

cmd += ["-map", "0:v", "-map", "0:a?"]

if quality != "Best":
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "23"]
else:
    cmd += ["-c:v", "copy"]

cmd += [
    "-c:a", "aac",
    "-b:a", "128k",
    "-movflags", "+faststart",
    "-progress", "pipe:1",
    "-nostats",
    output_file,
]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    rec["proc"] = proc

    last_update   = time.time()
    progress_buf  = ""
    progress_data: dict = {}
    start         = time.time()
    height        = quality_to_height(quality)
    audio_display = ", ".join(audio_tracks) if audio_tracks else "Default"

    async def read_progress():
        nonlocal last_update, progress_buf, progress_data
        while True:
            chunk = await proc.stdout.read(256)
            if not chunk:
                break
            progress_buf += chunk.decode("utf-8", errors="ignore")
            progress_data.update(parse_ffmpeg_progress(progress_buf))

            now = time.time()
            if now - last_update < 5:
                continue
            last_update = now
            elapsed = now - start

            out_time_str = progress_data.get("out_time", "00:00:00.000000")
            try:
                tp = out_time_str.split(":")
                recorded_sec = int(tp[0]) * 3600 + int(tp[1]) * 60 + float(tp[2])
            except Exception:
                recorded_sec = 0

            pct = min(100.0, recorded_sec / duration_sec * 100) if duration_sec > 0 else 0.0
            dots = "●" * int(pct / 10) + "○" * (10 - int(pct / 10))

            try:
                size_mb = int(progress_data.get("total_size", "0")) / (1024 * 1024)
            except Exception:
                size_mb = 0.0

            speed_raw = progress_data.get("speed", "N/A").strip()
            speed = speed_raw if speed_raw and speed_raw != "N/A" else "N/A"

            eta_str = "N/A"
            if 0 < pct < 100 and elapsed > 0:
                eta_str = fmt_duration(int((100 - pct) / pct * elapsed))

            bitrate = progress_data.get("bitrate", "").strip().replace("kbits/s", "K")
            res_display = bitrate if bitrate and bitrate not in ("N/A", "") else (
                "Best" if quality == "Best" else f"{height}p"
            )

            status_text = (
                f"📡 **Title:** Stream\n"
                f"✅ **Res:** {res_display} | AR: {aspect}\n"
                f"🎵 **Audio:** {audio_display}\n\n"
                f"📡 **Status:** Record\n"
                f"{dots} {pct:.1f}%\n"
                f"💾 **Size:** {size_mb:.2f}MB\n"
                f"⚡ **Speed:** {speed}\n"
                f"⏳ **ETA:** {eta_str}"
            )
            try:
                await status_msg.edit_text(status_text)
            except Exception:
                pass

    prog_task = asyncio.create_task(read_progress())
    await proc.wait()
    prog_task.cancel()
    return proc.returncode

# ─────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    uid  = message.from_user.id
    name = message.from_user.first_name or "Dost"
    args = message.text.split(None, 1)
    param = args[1].strip() if len(args) > 1 else ""

    # ── Verification deep link: /start verify_<token> ──
    if param.startswith("verify_"):
        token = param[7:]   # strip "verify_"
        entry = verify_tokens.get(token)
        if not entry:
            return await message.reply(
                "❌ **Invalid or expired verification link.**\n\n"
                "Please send any command again to get a new link."
            )
        token_uid = entry["uid"]
        if token_uid != uid:
            return await message.reply("❌ This verification link is not for you.")
        # Mark verified
        expiry = storage.add_verified(uid, name, VERIFY_HOURS)
        del verify_tokens[token]
        return await message.reply(
            f"✅ **{name} has successfully verified!**\n\n"
            f"🔓 Recording features unlocked for **{VERIFY_HOURS} hours**\n"
            f"⏰ Access expires: `{expiry.strftime('%d-%m-%Y %I:%M %p')}`\n\n"
            f"Ab /record ya /Channels use karo! 🎬"
        )

    dosts = storage.dost_count()
    verify_status = "🟢 ON" if storage.is_verification_enabled() else "🔴 OFF"
    text = (
        f"👋 **Salaam ༺ {name} ༻!**\n\n"
        f"👥 Abhi **{dosts}** Dost registered hain\n"
        f"🔐 Verification: **{verify_status}**\n\n"
        f"📋 **Commands:**\n"
        f"• /record `<url> <HH:MM:SS>` — M3U8 stream record karo\n"
        f"• /download_OTT `<url>` — OTT video download karo\n"
        f"• /set_cookies — Login cookies set karo\n"
        f"• /cookies_status — Cookies status dekho\n"
        f"• /del_cookies — Cookies delete karo\n"
        f"• /Channels — Channel links dekho aur record karo\n"
        f"• /PlaylistChannels — Playlist se channels browse karo (Kids/Movies/Sports)\n"
        f"• /search `<name>` — Playlist me channel search karo\n"
        f"• /verify — Verification link lo (free users)\n"
        f"• /Add_dost — Kisi ko Dost add karo\n"
        f"• /dost_list — Saare Dost dekho\n"
        f"• /remove_dost — Dost hatao *(Owner only)*\n"
        f"• /verifyon — Verification enable karo *(Owner only)*\n"
        f"• /verifyoff — Verification disable karo *(Owner only)*\n"
        f"• /verifystatus — Verification status dekho *(Owner only)*\n"
        f"• /mera_id — Apna ID dekho\n"
        f"• /compress — File ya video compress karo\n"
        f"🔹 /statusme — Check your active recordings\n"
        f"🔹 /cancelme — Cancel your active recordings\n\n"
        f"/plan — See subscription options\n\n"
        f"🆓 **Free User Limits**\n"
        f"• Max recording duration: **{FREE_MAX_DURATION_HOURS} hours**\n"
        f"• Max links per group: **{FREE_MAX_GROUP_LINKS}**\n"
        f"• Max concurrent links per user: **{MAX_RECORDINGS}**\n\n"
        f"💎 **Premium**\n"
        f"⏱ Time Limit: Up to 2 hours\n"
        f"👤 Concurrent Tasks: Up to 5\n"
        f"🔗 Group Limit: Unlimited\n"
        f"🔓 Verification: Not Required\n\n"
        f"💰 1 Week $25 | 15 Days $50 | 1 Month $75\n\n"
        f"**Example 1:**\n`/record http://example.com/live.m3u8 01:30:00`\n\n"
        f"**Example 2:**\n`/download_OTT https://discoveryplus.in/videos/...`\n\n"
        f"**Example 3:**\n`/record Pogo 00:05:00`"
    )
    await message.reply(text)

# ─────────────────────────────────────────────
#  /verify  (user command — get verification link)
# ─────────────────────────────────────────────

@app.on_message(filters.command("verify"))
async def cmd_verify(client: Client, message: Message):
    uid = message.from_user.id
    if is_owner(uid) or uid in AUTH_USERS or storage.is_dost(uid) or storage.is_premium(uid):
        return await message.reply("✅ **You don't need to verify.** You already have full access!")
    if not storage.is_verification_enabled():
        return await message.reply("✅ **Verification is not required right now.** You have free access!")
    if storage.is_verified(uid):
        expiry = storage.verified_expiry(uid)
        exp_str = expiry.strftime('%d-%m-%Y %I:%M %p') if expiry else "?"
        return await message.reply(
            f"✅ **Already Verified!**\n\n"
            f"🔓 Your access is active until: `{exp_str}`\n\n"
            f"Ab /record ya /Channels use karo! 🎬"
        )
    await send_verification_message(message, uid)

# ─────────────────────────────────────────────
#  /Channels
# ─────────────────────────────────────────────

@app.on_message(filters.command("Channels"))
async def cmd_channels(client: Client, message: Message):
    uid = message.from_user.id
    if needs_verification(uid):
        return await send_verification_message(message, uid)

    args = message.text.split(None, 1)
    duration_str = args[1].strip() if len(args) > 1 else ""

    channel_pending[uid] = {
        "duration_str": duration_str,
        "chat_id":      message.chat.id,
    }

    await message.reply(
        "📡 **Available Channels**\n\nChannel choose karo — phir source (TPlay/JioTV) select karo:",
        reply_markup=build_channels_keyboard(),
    )


# ─────────────────────────────────────────────
#  /record  (URL or channel name)
# ─────────────────────────────────────────────

@app.on_message(filters.command("record"))
async def cmd_record(client: Client, message: Message):
    uid = message.from_user.id

    if is_blocked(uid) and not is_owner(uid):
        return await message.reply(
            "❌ **Aap block ho.**\n"
            "1 ghante ke baad try karo."
        )

    if needs_verification(uid):
        return await send_verification_message(message, uid)

    # Parse: /record <url_or_channel_name> <HH:MM:SS>
    # Duration is always the LAST token; everything in between is the link/name.
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply(
            "⚠️ **Usage:**\n"
            "`/record <url> <HH:MM:SS>`\n"
            "`/record <channel name> <HH:MM:SS>`\n\n"
            "**Examples:**\n"
            "`/record http://example.com/live.m3u8 01:30:00`\n"
            "`/record Pogo 00:05:00`\n"
            "`/record Cartoon Network 01:00:00`"
        )

    duration_str    = parts[-1]
    link_or_name    = " ".join(parts[1:-1])

    try:
        duration_sec = parse_duration(duration_str)
    except Exception:
        return await message.reply("❌ Invalid duration. Use `HH:MM:SS`")

    # Resolve channel name → URL (checks default + custom channels)
    all_channels = storage.get_all_channels()
    ch = all_channels.get(link_or_name.strip().lower())
    if ch:
        # Multiple sources → ask which one
        channel_pending[uid] = {
            "duration_str": duration_str,
            "duration_sec": duration_sec,
            "chat_id":      message.chat.id,
        }
        sources = ch["sources"]
        canonical_key = link_or_name.strip().lower()
        btns = [
            [InlineKeyboardButton(f"📡 {src}", callback_data=f"src_{canonical_key}_{src}")]
            for src in sources
        ]
        btns.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")])
        return await message.reply(
            f"📺 **{ch['emoji']} {ch['name']}**\n\n"
            f"⏱ Duration: `{duration_str}`\n\n"
            f"Source choose karo:",
            reply_markup=InlineKeyboardMarkup(btns),
        )

    # Must be a direct URL
    if not link_or_name.startswith("http"):
        return await message.reply(
            f"❌ Channel **{link_or_name}** not found.\n\n"
            f"Available: /Channels\n"
            f"Or use a direct URL."
        )

    link = link_or_name

    # Duration limit for free users
    if not is_owner(uid) and not storage.is_premium(uid) and uid not in AUTH_USERS:
        if duration_sec > FREE_MAX_DURATION_HOURS * 3600:
            return await message.reply(
                f"⛔ Free users max **{FREE_MAX_DURATION_HOURS} hours**.\n"
                f"Use /plan to upgrade."
            )

    # Concurrent/spam check
    count = active_count(uid)
    if count >= MAX_RECORDINGS and not is_owner(uid):
        warnings = user_warnings.get(uid, 0) + 1
        user_warnings[uid] = warnings
        if warnings >= 3:
            blocked_users[uid] = time.time() + BLOCK_DURATION
            for rec in active.get(uid, []):
                cancel_recording(uid, rec)
            active[uid] = []
            return await message.reply(
                "🚫 **Spam detected!**\n"
                "User blocked for **1 hour**.\n"
                "All active recordings cancelled."
            )
        return await message.reply(
            f"⚠️ **Warning ({warnings}/3)**\n"
            f"Abhi **{count}** recording(s) chal rahi hain.\n"
            f"Pahle complete hone do. Max: **{MAX_RECORDINGS}**"
        )

    user_warnings[uid] = 0
    _setup_pending(uid, link, duration_sec, duration_str, message.chat.id)
    await message.reply(
        f"🎬 **/record link**\n\n🔗 `Hide Link`\n⏱ Duration: `{duration_str}`\n\nChoose your settings:",
        reply_markup=build_record_keyboard(uid),
    )

def _setup_pending(uid, link, duration_sec, duration_str, chat_id):
    pending[uid] = {
        "link":         link,
        "duration_sec": duration_sec,
        "duration_str": duration_str,
        "quality":      "720p",
        "aspect":       "Original",
        "audio":        [],
        "chat_id":      chat_id,
    }

# ─────────────────────────────────────────────
#  Callbacks
# ─────────────────────────────────────────────

@app.on_callback_query()
async def handle_callbacks(client: Client, query: CallbackQuery):
    uid  = query.from_user.id
    data = query.data

    if data == "noop":
        await query.answer()
        return

    # ── Playlist: close ──
    if data == "pl_close":
        await query.answer()
        await query.message.delete()
        return

    # ── Playlist: category / page navigation  pl_c_<cat>_<page> ──
    if data.startswith("pl_c_"):
        parts    = data[5:].rsplit("_", 1)
        category = parts[0] if len(parts) == 2 else "All"
        try:
            page = int(parts[1]) if len(parts) == 2 else 0
        except ValueError:
            page = 0
        await query.answer(f"📂 {category}")
        channels = await asyncio.get_event_loop().run_in_executor(None, playlist_mgr.get_channels)
        filtered = playlist_mgr.filter_channels(channels, category)
        keyboard = build_playlist_keyboard(category, page, filtered)
        cat_label = f"[{category}]" if category != "All" else "All"
        await query.message.edit_text(
            f"📺 **Playlist Channels** — {cat_label} ({len(filtered)} channels)\n"
            f"Select a channel to start recording:",
            reply_markup=keyboard,
        )
        return

    # ── Playlist: channel selected  pl_i_<idx> ──
    if data.startswith("pl_i_"):
        try:
            idx = int(data[5:])
        except ValueError:
            return await query.answer("Invalid channel.", show_alert=True)
        ch = await asyncio.get_event_loop().run_in_executor(
            None, playlist_mgr.get_by_idx, idx
        )
        if not ch:
            return await query.answer("Channel not found.", show_alert=True)
        if needs_verification(uid):
            await query.answer()
            await query.message.delete()
            return await send_verification_message(query.message, uid)
        # Ask user for duration — store channel info in awaiting state
        awaiting_pl_dur[uid] = {
            "ch":      ch,
            "chat_id": query.message.chat.id,
        }
        pending.pop(uid, None)
        await query.answer(f"📺 {ch['name']}")
        await query.message.edit_text(
            f"📺 **{ch['name']}**\n"
            f"📂 Group: `{ch['group']}`\n\n"
            f"⏱ **Enter recording duration** (format: `HH:MM:SS`)\n"
            f"Example: `01:30:00` for 1.5 hours\n\n"
            f"Type and send the duration below 👇",
        )
        return

    # ── Record setup: quality ──
    if data.startswith("q_"):
        if uid not in pending:
            return await query.answer("Session expired. Use /record again.", show_alert=True)
        pending[uid]["quality"] = data[2:]
        await query.answer(f"Quality: {data[2:]}")
        await query.message.edit_reply_markup(build_record_keyboard(uid))
        return

    # ── Aspect ratio ──
    if data.startswith("ar_"):
        if uid not in pending:
            return await query.answer("Session expired.", show_alert=True)
        pending[uid]["aspect"] = data[3:]
        await query.answer(f"Aspect: {data[3:]}")
        await query.message.edit_reply_markup(build_record_keyboard(uid))
        return

    # ── Audio tracks ──
    if data.startswith("a_"):
        if uid not in pending:
            return await query.answer("Session expired.", show_alert=True)
        track = data[2:]
        sel   = pending[uid].setdefault("audio", [])
        if track == "All Tracks":
            pending[uid]["audio"] = ["All Tracks"]
        else:
            if "All Tracks" in sel:
                sel.remove("All Tracks")
            if track in sel:
                sel.remove(track)
            else:
                sel.append(track)
        added = track in pending[uid]["audio"]
        await query.answer(f"{'Added' if added else 'Removed'}: {track}")
        await query.message.edit_reply_markup(build_record_keyboard(uid))
        return

    # ── Cancel record setup ──
    if data == "cancel_setup":
        pending.pop(uid, None)
        channel_pending.pop(uid, None)
        await query.answer("Cancelled.")
        await query.message.delete()
        return

    # ── Start recording ──
    if data == "start_record":
        if uid not in pending:
            return await query.answer("Session expired. Use /record again.", show_alert=True)
        await query.answer("⚡ Starting...")
        await query.message.delete()
        s = pending.pop(uid)
        asyncio.create_task(do_record(client, uid, s))
        return

    # ── Channel list button ──
    if data.startswith("ch_"):
        channel_key = data[3:]
        ch = storage.get_all_channels().get(channel_key)
        if not ch:
            return await query.answer("Channel not found.", show_alert=True)
        await query.answer()
        await query.message.edit_text(
            f"📺 **{ch['emoji']} {ch['name']}**\n\nSource choose karo:",
            reply_markup=build_source_keyboard(channel_key),
        )
        return

    # ── Channels: back button ──
    if data == "channels_back":
        await query.answer()
        await query.message.edit_text(
            "📡 **Available Channels**\n\nChannel choose karo:",
            reply_markup=build_channels_keyboard(),
        )
        return

    # ── Source selected (from /Channels or /record channel name) ──
    if data.startswith("src_"):
        # format: src_<channel_key>_<SourceName>
        rest        = data[4:]
        parts       = rest.split("_", 1)
        channel_key = parts[0]
        source_name = parts[1] if len(parts) > 1 else ""

        ch = storage.get_all_channels().get(channel_key)
        if not ch:
            return await query.answer("Channel not found.", show_alert=True)

        link = ch["sources"].get(source_name)
        if not link:
            return await query.answer("Source not found.", show_alert=True)

        cp   = channel_pending.pop(uid, {})
        duration_str = cp.get("duration_str", "01:00:00")
        chat_id      = cp.get("chat_id", query.message.chat.id)

        try:
            duration_sec = parse_duration(duration_str)
        except Exception:
            duration_sec = 3600

        # Concurrent/spam check
        count = active_count(uid)
        if count >= MAX_RECORDINGS and not is_owner(uid):
            warnings = user_warnings.get(uid, 0) + 1
            user_warnings[uid] = warnings
            if warnings >= 3:
                blocked_users[uid] = time.time() + BLOCK_DURATION
                for rec in active.get(uid, []):
                    cancel_recording(uid, rec)
                active[uid] = []
                await query.answer("🚫 Spam! Blocked 1 hour.", show_alert=True)
                await query.message.edit_text("🚫 **Spam detected!** Blocked for 1 hour.")
                return
            await query.answer(f"⚠️ Warning {warnings}/3 — Max {MAX_RECORDINGS} recordings.", show_alert=True)
            return

        user_warnings[uid] = 0
        _setup_pending(uid, link, duration_sec, duration_str, chat_id)

        await query.answer("⚡ Settings choose karo!")
        await query.message.edit_text(
            f"🎬 **{ch['emoji']} {ch['name']}** — {source_name}\n\n"
            f"🔗 `Hide Link`\n⏱ Duration: `{duration_str}`\n\nChoose your settings:",
            reply_markup=build_record_keyboard(uid),
        )
        return

    # ── Cancel individual recording ──
    if data.startswith("cancel_rec_"):
        idx  = int(data.split("_")[-1])
        recs = active.get(uid, [])
        if idx < len(recs):
            cancel_recording(uid, recs[idx])
            recs.pop(idx)
            await query.answer("Recording cancelled.")
            await query.message.edit_text("❌ Recording cancelled.")
        else:
            await query.answer("Recording not found.")
        return

    # ── Cancel all ──
    if data == "cancel_all":
        recs = active.pop(uid, [])
        for rec in recs:
            cancel_recording(uid, rec)
        await query.answer(f"{len(recs)} recording(s) cancelled.")
        await query.message.edit_text(f"⛔ **{len(recs)} recording(s) cancelled.**")
        return

    # ── /statusme Refresh ──
    if data == "statusme_refresh":
        username = query.from_user.username or ""
        text     = _build_statusme_text(uid, username)
        await query.answer("↻ Refreshed!")
        try:
            await query.message.edit_text(text, reply_markup=_statusme_keyboard())
        except Exception:
            pass
        return

    # ── /statusme Close ──
    if data == "statusme_close":
        await query.answer("Closed.")
        await query.message.delete()
        return

# ─────────────────────────────────────────────
#  Recording coroutine
# ─────────────────────────────────────────────

async def do_record(client: Client, uid: int, s: dict):
    link         = s["link"]
    duration_sec = s["duration_sec"]
    quality      = s["quality"]
    aspect       = s["aspect"]
    audio_tracks = s.get("audio", [])
    chat_id      = s["chat_id"]
    output_file  = build_output_filename(quality, audio_tracks)

    status_msg = await client.send_message(
        chat_id,
        "🔧 **Initializing recording process. Please wait...**"
    )

    rec = {
        "proc":         None,
        "task":         asyncio.current_task(),
        "status_msg":   status_msg,
        "output_file":  output_file,
        "start_time":   time.time(),
        "duration_sec": duration_sec,
        "duration_str": s.get("duration_str", ""),
        "link":         link,
        "quality":      quality,
        "aspect":       aspect,
        "audio":        audio_tracks,
        "chat_id":      chat_id,
    }

    active.setdefault(uid, []).append(rec)

    try:
        ret = await run_ffmpeg_record(
            client, uid, rec,
            link, duration_sec, output_file,
            quality, aspect, audio_tracks,
        )

        if uid not in active or rec not in active.get(uid, []):
            return  # cancelled

        if ret != 0 or not os.path.exists(output_file):
            await status_msg.edit_text(
                "❌ **Recording failed.**\n"
                "Link check karo — stream accessible hai?"
            )
            return

        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        await status_msg.edit_text(
            f"🚀 **Uploading...**\n\n"
            f"💾 Size: {size_mb:.2f} MB"
        )

        await client.send_video(
            chat_id=chat_id,
            video=output_file,
            caption=(
                f"✅ **Recording Complete!**\n\n"
                f"📁 `{output_file}`\n"
                f"💾 Size: {size_mb:.2f} MB\n\n"
                f"🔹 Credits: @{CHANNEL_TAG}"
            ),
            supports_streaming=True,
        )
        await status_msg.delete()

    except asyncio.CancelledError:
        try:
            await status_msg.edit_text("❌ Recording was cancelled.")
        except Exception:
            pass
    except Exception as e:
        try:
            await status_msg.edit_text(f"❌ Error: {e}")
        except Exception:
            pass
    finally:
        try:
            active.get(uid, []).remove(rec)
        except ValueError:
            pass
        if not active.get(uid):
            active.pop(uid, None)
        if os.path.exists(output_file):
            os.remove(output_file)

# ─────────────────────────────────────────────
#  /download_OTT
# ─────────────────────────────────────────────

@app.on_message(filters.command("download_OTT"))
async def cmd_download_ott(client: Client, message: Message):
    uid  = message.from_user.id
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply(
            "⚠️ **Usage:** `/download_OTT <url>`\n\n"
            "**Example:**\n`/download_OTT https://discoveryplus.in/videos/...`"
        )

    if needs_verification(uid):
        return await send_verification_message(message, uid)

    link = args[1].strip()

    if active_count(uid) >= MAX_RECORDINGS and not is_owner(uid):
        return await message.reply(f"⚠️ You have {active_count(uid)} active tasks. Max: {MAX_RECORDINGS}")

    status_msg = await message.reply("⬇️ **Downloading OTT content...**")

    rec = {
        "proc": None, "task": None, "status_msg": status_msg,
        "output_file": "", "start_time": time.time(), "link": link,
        "quality": "OTT", "aspect": "-", "audio": [], "chat_id": message.chat.id,
    }
    active.setdefault(uid, []).append(rec)
    task = asyncio.create_task(do_download_ott(client, uid, rec, link, status_msg, message.chat.id))
    rec["task"] = task

async def do_download_ott(client: Client, uid: int, rec: dict, link: str,
                           status_msg: Message, chat_id: int):
    yt_cmd = ["yt-dlp", "--no-warnings", "-o", "%(title)s.%(ext)s",
               "--merge-output-format", "mp4", "--newline"]
    if os.path.exists("cookies.txt"):
        yt_cmd += ["--cookies", "cookies.txt"]
    yt_cmd.append(link)

    output_file = None
    try:
        proc = await asyncio.create_subprocess_exec(
            *yt_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        rec["proc"] = proc
        last_update = time.time()

        async for line in proc.stdout:
            decoded = line.decode("utf-8", errors="ignore").strip()
            if "[download]" in decoded and "%" in decoded and time.time() - last_update >= 4:
                last_update = time.time()
                try:
                    await status_msg.edit_text(f"⬇️ **Downloading OTT...**\n`{decoded[:200]}`")
                except Exception:
                    pass
            m = re.search(r"Destination: (.+)", decoded)
            if m:
                output_file = m.group(1).strip()

        await proc.wait()

        if not output_file:
            for f in sorted(os.listdir("."), key=os.path.getmtime, reverse=True):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    output_file = f
                    break

        if not output_file or not os.path.exists(output_file):
            return await status_msg.edit_text("❌ Download failed or file not found.")

        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        await status_msg.edit_text(f"🚀 **Uploading...**\n💾 {size_mb:.2f} MB")
        await client.send_video(
            chat_id=chat_id, video=output_file,
            caption=f"✅ **Download Complete!**\n📁 `{output_file}`\n🔹 Credits: @{CHANNEL_TAG}",
            supports_streaming=True,
        )
        await status_msg.delete()

    except asyncio.CancelledError:
        pass
    except Exception as e:
        try:
            await status_msg.edit_text(f"❌ Error: {e}")
        except Exception:
            pass
    finally:
        try:
            active.get(uid, []).remove(rec)
        except ValueError:
            pass
        if not active.get(uid):
            active.pop(uid, None)
        if output_file and os.path.exists(output_file):
            os.remove(output_file)

# ─────────────────────────────────────────────
#  /compress
# ─────────────────────────────────────────────

@app.on_message(filters.command("compress"))
async def cmd_compress(client: Client, message: Message):
    awaiting_compress[message.from_user.id] = True
    await message.reply(
        "📦 **Compress Mode**\n\n"
        "Send me a video or document to compress.\n"
        "I'll re-encode it at CRF 28 (smaller size, good quality)."
    )

@app.on_message(filters.video | filters.document)
async def handle_file_upload(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in awaiting_compress:
        return
    awaiting_compress.pop(uid)

    status_msg = await message.reply("⏳ **Downloading your file...**")
    file_path = out_file = None
    try:
        file_path = await client.download_media(message)
        out_file  = "compressed_" + os.path.basename(str(file_path))
        await status_msg.edit_text("⚙️ **Compressing...**")

        cmd = [
            "ffmpeg", "-y", "-i", str(file_path),
            "-c:v", "libx264", "-crf", "28", "-preset", "fast",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            out_file,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

        if not os.path.exists(out_file):
            return await status_msg.edit_text("❌ Compression failed.")

        orig_mb = os.path.getsize(file_path) / (1024 * 1024)
        comp_mb = os.path.getsize(out_file)  / (1024 * 1024)
        savings = max(0.0, (orig_mb - comp_mb) / orig_mb * 100) if orig_mb else 0.0

        await status_msg.edit_text(f"🚀 **Uploading...**\n💾 {comp_mb:.2f} MB")
        await client.send_video(
            chat_id=message.chat.id, video=out_file,
            caption=(
                f"✅ **Compressed!**\n"
                f"📥 Original: {orig_mb:.2f} MB\n"
                f"📤 Compressed: {comp_mb:.2f} MB\n"
                f"💡 Saved: {savings:.1f}%\n\n"
                f"🔹 Credits: @{CHANNEL_TAG}"
            ),
            supports_streaming=True,
        )
        await status_msg.delete()
    except Exception as e:
        try:
            await status_msg.edit_text(f"❌ Error: {e}")
        except Exception:
            pass
    finally:
        if file_path and os.path.exists(str(file_path)):
            os.remove(str(file_path))
        if out_file and os.path.exists(out_file):
            os.remove(out_file)

# ─────────────────────────────────────────────
#  Cookies commands
# ─────────────────────────────────────────────

@app.on_message(filters.command("set_cookies"))
async def cmd_set_cookies(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Only Owner can set cookies.")
    awaiting_cookies[message.from_user.id] = True
    await message.reply(
        "🍪 **Set Cookies**\n\n"
        "Send me a Netscape cookies.txt file or paste cookie content as text."
    )

@app.on_message(filters.command("cookies_status"))
async def cmd_cookies_status(client: Client, message: Message):
    cookies = storage.get_cookies()
    if cookies:
        lines = cookies.strip().split("\n")
        await message.reply(
            f"✅ **Cookies are set!**\n"
            f"📄 Lines: {len(lines)}\n"
            f"📝 Preview:\n`{lines[0][:80]}`"
        )
    else:
        await message.reply("❌ **No cookies set.**\nUse /set_cookies to add them.")

@app.on_message(filters.command("del_cookies"))
async def cmd_del_cookies(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Only Owner can delete cookies.")
    storage.delete_cookies()
    await message.reply("✅ **Cookies deleted.**")

# ─────────────────────────────────────────────
#  Dost management
# ─────────────────────────────────────────────

@app.on_message(filters.command("Add_dost"))
async def cmd_add_dost(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Only Owner can add Dost.")
    awaiting_dost[message.from_user.id] = True
    await message.reply(
        "👥 **Add Dost**\n\n"
        "Forward a message from the user you want to add as Dost,\n"
        "or send their User ID directly."
    )

@app.on_message(filters.forwarded)
async def handle_forwarded(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in awaiting_dost:
        return
    awaiting_dost.pop(uid)
    fwd = message.forward_from
    if not fwd:
        return await message.reply(
            "❌ Could not get user info. Their privacy settings may block this.\n"
            "Ask them to send their ID using /mera_id, then send it here."
        )
    storage.add_dost(fwd.id, fwd.username or fwd.first_name or str(fwd.id), uid)
    await message.reply(
        f"✅ **{fwd.first_name}** (`{fwd.id}`) added as Dost!\n"
        f"👥 Total Dosts: {storage.dost_count()}"
    )

@app.on_message(filters.command("dost_list"))
async def cmd_dost_list(client: Client, message: Message):
    dosts = storage.get_dosts()
    if not dosts:
        return await message.reply("👥 **No Dosts registered.**\nUse /Add_dost to add one.")
    lines = [f"👥 **Dost List** ({len(dosts)} total)\n"]
    for i, (did, info) in enumerate(dosts.items(), 1):
        uname    = info.get("username", "Unknown")
        added_at = info.get("added_at", "?")[:10]
        lines.append(f"{i}. **{uname}** | `{did}` | {added_at}")
    await message.reply("\n".join(lines))

@app.on_message(filters.command("remove_dost"))
async def cmd_remove_dost(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Only Owner can remove Dost.")
    args = message.text.split(None, 1)
    if len(args) < 2:
        return await message.reply("⚠️ **Usage:** `/remove_dost <user_id>`")
    try:
        target = int(args[1].strip())
    except ValueError:
        return await message.reply("❌ Invalid user ID.")
    if storage.remove_dost(target):
        await message.reply(f"✅ Dost `{target}` removed.\n👥 Total: {storage.dost_count()}")
    else:
        await message.reply(f"❌ User `{target}` is not in Dost list.")

# ─────────────────────────────────────────────
#  /mera_id
# ─────────────────────────────────────────────

@app.on_message(filters.command("mera_id"))
async def cmd_mera_id(client: Client, message: Message):
    uid   = message.from_user.id
    uname = message.from_user.username or message.from_user.first_name
    plan  = "💎 Premium" if storage.is_premium(uid) else "🆓 Free"
    expiry = storage.premium_expiry(uid)
    expiry_str = f"\n⏳ Expires: `{expiry.strftime('%d-%m-%Y')}`" if expiry else ""
    role = "👑 Owner" if is_owner(uid) else ("✅ Dost" if storage.is_dost(uid) else "👤 User")
    await message.reply(
        f"🪪 **Your Profile**\n\n"
        f"👤 Name: **{uname}**\n"
        f"🆔 ID: `{uid}`\n"
        f"📦 Plan: {plan}{expiry_str}\n"
        f"🎖 Role: {role}"
    )


# ─────────────────────────────────────────────
#  /cancelme  /stop
# ─────────────────────────────────────────────

@app.on_message(filters.command(["cancelme", "stop"]))
async def cmd_cancelme(client: Client, message: Message):
    uid  = message.from_user.id
    recs = active.pop(uid, [])
    if not recs:
        return await message.reply("✅ No active recordings to cancel.")
    for rec in recs:
        cancel_recording(uid, rec)
    await message.reply(f"⛔ **{len(recs)} recording(s) stopped.**")

# ─────────────────────────────────────────────
#  /plan
# ─────────────────────────────────────────────

@app.on_message(filters.command("plan"))
async def cmd_plan(client: Client, message: Message):
    uid    = message.from_user.id
    expiry = storage.premium_expiry(uid)
    expiry_str = f"✅ **Your Premium expires:** `{expiry.strftime('%d-%m-%Y %H:%M')}`\n\n" if expiry else ""
    await message.reply(
        f"💎 **Premium Plans**\n\n"
        f"{expiry_str}"
        f"⏱ Time Limit: Up to **2 hours**\n"
        f"👤 Concurrent Tasks: Up to **{MAX_RECORDINGS}**\n"
        f"🔗 Group Limit: **Unlimited**\n"
        f"🔓 Verification: **Not Required**\n\n"
        f"💰 **Pricing:**\n"
        f"• 1 Week  — **$25**\n"
        f"• 15 Days — **$50**\n"
        f"• 1 Month — **$75**\n\n"
        f"📩 Contact: {GROUP_LINK}"
    )

# ─────────────────────────────────────────────
#  Owner commands
# ─────────────────────────────────────────────

@app.on_message(filters.command("add_premium"))
async def cmd_add_premium(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    args = message.text.split()
    if len(args) < 3:
        return await message.reply("⚠️ **Usage:** `/add_premium <user_id> <days>`")
    try:
        target_id = int(args[1])
        days      = int(args[2])
    except ValueError:
        return await message.reply("❌ Invalid user_id or days.")
    expiry = storage.add_premium(target_id, days)
    await message.reply(
        f"✅ **Premium added!**\n"
        f"👤 User: `{target_id}`\n"
        f"📅 Days: {days}\n"
        f"⏳ Expires: `{expiry.strftime('%d-%m-%Y %H:%M')}`"
    )

@app.on_message(filters.command("user_unblock"))
async def cmd_user_unblock(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ **Usage:** `/user_unblock <user_id>`")
    try:
        uid = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID.")
    blocked_users.pop(uid, None)
    user_warnings[uid] = 0
    await message.reply(f"✅ User `{uid}` unblocked.")

@app.on_message(filters.command("block_list"))
async def cmd_block_list(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return
    now     = time.time()
    expired = [uid for uid, t in blocked_users.items() if now > t]
    for uid in expired:
        del blocked_users[uid]
    if not blocked_users:
        return await message.reply("✅ Koi user block nahi hai.")
    lines = ["🚫 **Blocked Users**\n"]
    for uid, t in blocked_users.items():
        remaining = int((t - now) / 60)
        lines.append(f"• `{uid}` — unblock in **{remaining} min**")
    await message.reply("\n".join(lines))

@app.on_message(filters.command("user_dost_cancel"))
async def cmd_user_dost_cancel(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ **Usage:** `/user_dost_cancel <user_id>`")
    try:
        target = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID.")
    recs = active.pop(target, [])
    for rec in recs:
        cancel_recording(target, rec)
    await message.reply(f"⛔ All recordings cancelled for user `{target}`. ({len(recs)} stopped)")

# ─────────────────────────────────────────────
#  /verifyon  /verifyoff  (Owner only)
# ─────────────────────────────────────────────

@app.on_message(filters.command("verifyon"))
async def cmd_verifyon(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    storage.set_verification_enabled(True)
    await message.reply(
        "✅ **Verification ON**\n\n"
        "Free users will now need to verify via shortener link before using bot features.\n"
        "Owners, Auth users, Dosts and Premium users are exempt."
    )

@app.on_message(filters.command("verifyoff"))
async def cmd_verifyoff(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    storage.set_verification_enabled(False)
    await message.reply(
        "🔴 **Verification OFF**\n\n"
        "All users can now use the bot freely without verification."
    )

@app.on_message(filters.command("verifystatus"))
async def cmd_verifystatus(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    status = "🟢 ON" if storage.is_verification_enabled() else "🔴 OFF"
    await message.reply(f"🔐 **Verification Status:** {status}")

# ─────────────────────────────────────────────
#  /Owner_verify  /Owner_verified  (Owner toggles own verification exemption)
# ─────────────────────────────────────────────

@app.on_message(filters.command("Owner_verify"))
async def cmd_owner_verify(client: Client, message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        return  # silently ignore non-owners
    # Add owner to verified list with a 50-year expiry (permanent)
    name   = message.from_user.first_name or str(uid)
    expiry = storage.add_verified(uid, name, hours=50 * 365 * 24)
    await message.reply(
        f"✅ **Owner Verified!**\n\n"
        f"👑 Aap ab verified hain.\n"
        f"🔓 Verification system se hamesha exempt rahenge.\n\n"
        f"Undo karne ke liye: `/Owner_verified`"
    )

@app.on_message(filters.command("Owner_verified"))
async def cmd_owner_verified(client: Client, message: Message):
    uid = message.from_user.id
    if not is_owner(uid):
        return  # silently ignore non-owners
    removed = storage.remove_verified(uid)
    if removed:
        await message.reply(
            f"🔐 **Owner Verification Removed!**\n\n"
            f"👑 Aap ab verified list se hata diye gaye hain.\n"
            f"⚠️ Agar verification ON hai, aapko bhi `/verify` karna padega.\n\n"
            f"Wapas add karne ke liye: `/Owner_verify`"
        )
    else:
        await message.reply(
            f"ℹ️ **Aap already verified list me nahi hain.**\n\n"
            f"Khud ko add karne ke liye: `/Owner_verify`"
        )

# ─────────────────────────────────────────────
#  /Verifying_add  /Verifying_remove  /Verifying_list  (Owner)
# ─────────────────────────────────────────────

@app.on_message(filters.command("Verifying_add"))
async def cmd_verifying_add(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    args = message.text.split(None, 2)
    if len(args) < 2:
        return await message.reply(
            "⚠️ **Usage:** `/Verifying_add <user_id> [name]`\n\n"
            "Add a user to the verified list (30 days access)."
        )
    try:
        target_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID.")
    name   = args[2].strip() if len(args) > 2 else str(target_id)
    expiry = storage.add_verified(target_id, name, hours=30 * 24)   # 30 days
    await message.reply(
        f"✅ **User Added to Verified List!**\n\n"
        f"👤 User ID: `{target_id}`\n"
        f"📛 Name: {name}\n"
        f"📅 Access until: `{expiry.strftime('%d-%m-%Y')}`"
    )

@app.on_message(filters.command("Verifying_remove"))
async def cmd_verifying_remove(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚠️ **Usage:** `/Verifying_remove <user_id>`")
    try:
        target_id = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid user ID.")
    removed = storage.remove_verified(target_id)
    if removed:
        await message.reply(f"🗑 **Removed** user `{target_id}` from verified list.")
    else:
        await message.reply(f"⚠️ User `{target_id}` was not in the verified list.")

@app.on_message(filters.command("PlaylistChannels"))
async def cmd_playlist_channels(client: Client, message: Message):
    uid = message.from_user.id
    if needs_verification(uid):
        return await send_verification_message(message, uid)
    msg = await message.reply("📡 **Loading playlist…** Please wait.")
    channels = await asyncio.get_event_loop().run_in_executor(None, playlist_mgr.get_channels)
    if not channels:
        return await msg.edit_text("❌ **Failed to load playlist.** Try again later.")
    filtered = playlist_mgr.filter_channels(channels, "All")
    keyboard  = build_playlist_keyboard("All", 0, filtered)
    await msg.edit_text(
        f"📺 **Playlist Channels** — {len(filtered)} total\n"
        f"Choose a category, then select a channel to record:",
        reply_markup=keyboard,
    )

@app.on_message(filters.command("search"))
async def cmd_search(client: Client, message: Message):
    uid  = message.from_user.id
    if needs_verification(uid):
        return await send_verification_message(message, uid)
    args = message.text.split(None, 1)
    if len(args) < 2 or not args[1].strip():
        return await message.reply(
            "🔍 **Search Channels**\n\n"
            "Usage: `/search <channel name>`\n"
            "Example: `/search pogo`"
        )
    query = args[1].strip()
    msg   = await message.reply(f"🔍 Searching for **{query}**…")
    results = await asyncio.get_event_loop().run_in_executor(
        None, playlist_mgr.search_channels, query
    )
    if not results:
        return await msg.edit_text(f"❌ No channels found for **{query}**.\n\nTry a different keyword.")
    # Show up to 50 results as paginated keyboard
    keyboard = build_playlist_keyboard("All", 0, results)
    await msg.edit_text(
        f"🔍 **Search:** `{query}`\n"
        f"✅ Found **{len(results)}** channel(s):",
        reply_markup=keyboard,
    )

@app.on_message(filters.command("Verifying_list"))
async def cmd_verifying_list(client: Client, message: Message):
    if not is_owner(message.from_user.id):
        return await message.reply("❌ Owner only.")
    all_verified = storage.get_all_verified()
    if not all_verified:
        return await message.reply("📋 **Verified List is empty.**\n\nNo users have been verified yet.")
    now   = datetime.now()
    lines = ["📋 **Verified Users List**\n"]
    active_count_v = 0
    expired_count  = 0
    for uid, info in all_verified.items():
        try:
            expiry = datetime.fromisoformat(info["expiry"])
            is_active = expiry > now
        except Exception:
            is_active = False
        name     = info.get("name", "—")
        exp_str  = info.get("expiry", "?")[:16].replace("T", " ")
        status   = "🟢" if is_active else "🔴"
        if is_active:
            active_count_v += 1
        else:
            expired_count += 1
        lines.append(f"{status} `{uid}` — **{name}**\n   ⏰ Expires: `{exp_str}`")
    lines.append(f"\n✅ Active: **{active_count_v}** | ❌ Expired: **{expired_count}**")
    text = "\n".join(lines)
    # split if too long
    if len(text) > 4000:
        text = text[:4000] + "\n...(truncated)"
    await message.reply(text)

# ─────────────────────────────────────────────
#  /statusme — Active recording status (fancy)
# ─────────────────────────────────────────────

def _build_statusme_text(uid: int, username: str) -> str:
    recs = active.get(uid, [])
    if not recs:
        return "🎬 **Koi active recording nahi hai.**"
    show_link = uid in OWNER_IDS
    now = time.time()
    lines = [f"🎬 **Your Active Recording Tasks**\n"]
    for i, rec in enumerate(recs, start=1):
        start_ts    = rec.get("start_time", now)
        dur_sec     = rec.get("duration_sec", 0)
        dur_str     = rec.get("duration_str", "?")
        elapsed     = now - start_ts
        remaining   = max(0, dur_sec - elapsed)
        completed   = min(100, (elapsed / dur_sec * 100)) if dur_sec else 0
        filled      = int(completed / 10)
        bar         = "█" * filled + "░" * (10 - filled)
        start_dt    = datetime.fromtimestamp(start_ts).strftime("%d-%b-%Y %I:%M %p")
        end_dt      = datetime.fromtimestamp(start_ts + dur_sec).strftime("%d-%b-%Y %I:%M %p")
        rem_h       = int(remaining // 3600)
        rem_m       = int((remaining % 3600) // 60)
        rem_s       = int(remaining % 60)
        rem_fmt     = f"{rem_h:02d}:{rem_m:02d}:{rem_s:02d}"
        output_file = rec.get("output_file", "N/A")
        quality     = rec.get("quality", "N/A")
        aspect      = rec.get("aspect", "N/A")
        link_text   = rec.get("link", "") if show_link else "🔗 Hidden"
        uname       = f"@{username}" if username else f"ID:{uid}"
        lines.append(
            f"**Task #{i}**\n"
            f"👤 User: {uname}  |  🆔 `{uid}`\n"
            f"📁 File: `{output_file}`\n"
            f"🎞 Quality: `{quality}`  •  📐 Aspect: `{aspect}`\n"
            f"📅 Date: `{start_dt}`\n"
            f"▶️ Start: `{start_dt}`\n"
            f"⏹ End:   `{end_dt}`\n"
            f"🔗 Link: `{link_text}`\n"
            f"⏳ Duration: `{dur_str}`\n"
            f"⏱ Remaining: `{rem_fmt}`\n"
            f"📊 Progress: [{bar}] `{completed:.1f}%`\n"
        )
    lines.append(f"🕐 Refreshed: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
    return "\n".join(lines)

def _statusme_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("↻ Refresh", callback_data="statusme_refresh"),
        InlineKeyboardButton("✖ Close",   callback_data="statusme_close"),
    ]])

@app.on_message(filters.private & filters.command("statusme"))
async def cmd_statusme(client: Client, message: Message):
    uid      = message.from_user.id
    username = message.from_user.username or ""
    text     = _build_statusme_text(uid, username)
    await message.reply(text, reply_markup=_statusme_keyboard())

# ─────────────────────────────────────────────
#  Text / document router (cookies, dost IDs)
# ─────────────────────────────────────────────

@app.on_message(filters.private & filters.text & ~filters.command(""))
async def handle_text(client: Client, message: Message):
    uid = message.from_user.id
    if uid in awaiting_cookies:
        awaiting_cookies.pop(uid)
        storage.set_cookies(message.text)
        return await message.reply("✅ **Cookies saved successfully!**")
    if uid in awaiting_dost:
        awaiting_dost.pop(uid)
        try:
            target = int(message.text.strip())
            storage.add_dost(target, str(target), uid)
            return await message.reply(
                f"✅ User `{target}` added as Dost!\n"
                f"👥 Total: {storage.dost_count()}"
            )
        except ValueError:
            return await message.reply("❌ Invalid user ID. Send a numeric ID.")

    if uid in awaiting_pl_dur:
        info = awaiting_pl_dur.pop(uid)
        ch   = info["ch"]
        chat_id = info["chat_id"]
        duration_str = message.text.strip()
        try:
            duration_sec = parse_duration(duration_str)
            if duration_sec <= 0:
                raise ValueError
        except Exception:
            awaiting_pl_dur[uid] = info   # put back
            return await message.reply(
                "❌ Invalid duration format.\n"
                "Please send like: `01:30:00` (HH:MM:SS)"
            )
        # Check free user limit
        max_hrs = FREE_MAX_DURATION_HOURS
        if not (is_owner(uid) or uid in AUTH_USERS or storage.is_dost(uid) or storage.is_premium(uid)):
            if duration_sec > max_hrs * 3600:
                return await message.reply(
                    f"❌ **Duration too long!**\n"
                    f"Free users max: **{max_hrs} hours**.\n"
                    f"Use a shorter duration or upgrade to Premium."
                )
        _setup_pending(uid, ch["url"], duration_sec, duration_str, chat_id)
        await message.reply(
            f"🎬 **{ch['name']}**\n"
            f"📂 Group: `{ch['group']}`\n"
            f"🔗 `Hidden Link`\n"
            f"⏱ Duration: `{duration_str}`\n\n"
            f"Choose your recording settings:",
            reply_markup=build_record_keyboard(uid),
        )
        return

@app.on_message(filters.private & filters.document & ~filters.video)
async def handle_doc(client: Client, message: Message):
    uid = message.from_user.id
    if uid in awaiting_cookies:
        awaiting_cookies.pop(uid)
        file_path = await client.download_media(message)
        with open(str(file_path), "r", errors="ignore") as f:
            content = f.read()
        storage.set_cookies(content)
        os.remove(str(file_path))
        return await message.reply("✅ **Cookies file saved!**")
    if uid in awaiting_compress:
        await handle_file_upload(client, message)

# ─────────────────────────────────────────────
#  Run
# ─────────────────────────────────────────────

print("🚀 LittleSingham Bot Starting...")
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
print("🌐 Admin panel running on port 5000")
app.run()
