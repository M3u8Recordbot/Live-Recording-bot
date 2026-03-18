# m3u8_bot.py
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIG ---
API_ID = 29481626
API_HASH = "4892185769903521077c4cea97808b8c"
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 5856009289

# --- DATA STORAGE ---
dost_list = [1900583882]  # Pre-added friends
premium_users = {}         # user_id: expiry_time
verified_users = {}        # user_id: expiry_time
active_recordings = {}     # user_id: current_count

# --- HELPERS ---
def is_owner(user_id):
    return user_id == OWNER_ID

def is_verified(user_id):
    if is_owner(user_id):
        return True
    if user_id in verified_users and verified_users[user_id] > time.time():
        return True
    return False

def is_premium(user_id):
    if user_id in premium_users and premium_users[user_id] > time.time():
        return True
    return False

def get_user_limit(user_id):
    return 5 if is_premium(user_id) else 4

# --- APP ---
app = Client("M3u8LiveBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- COMMANDS ---

@app.on_message(filters.command("start"))
async def start(client, message):
    user_id = message.from_user.id
    verified = "ON" if is_verified(user_id) else "OFF"
    await message.reply_text(
        f"👋 Hello\n\n👥 Dost registered: {len(dost_list)}\n🔐 Verification: {verified}\n\n"
        "📋 Commands:\n"
        "• /record <link/name> <HH:MM:SS>\n"
        "• /Channels\n"
        "• /Add_dost <id>\n"
        "• /dost_list\n"
        "• /remove_dost <id> (Owner only)\n"
        "• /mera_id\n"
        "• /statusme\n"
        "• /cancelme\n"
        "• /plan\n"
        "• /search <channel>\n"
    )

@app.on_message(filters.command("record"))
async def record_cmd(client, message):
    user_id = message.from_user.id
    if not is_verified(user_id):
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Verify Now", url="https://t.me/M3u8LiveRecordingBot?start=verify")
        ]])
        return await message.reply("🔒 Verification required!", reply_markup=btn)

    args = message.command
    if len(args) < 3:
        return await message.reply("Usage: /record <channel_name/url> <HH:MM:SS>")

    channel_or_url = args[1]
    duration = args[2]
    url = CHANNELS.get(channel_or_url, channel_or_url)

    limit = get_user_limit(user_id)
    current = active_recordings.get(user_id, 0)
    if current >= limit:
        return await message.reply(f"❌ Max recordings reached ({limit})")

    active_recordings[user_id] = current + 1
    await message.reply(f"⏳ Recording started: {channel_or_url} for {duration}")
    # yahan FFmpeg call karenge

@app.on_message(filters.command("Channels"))
async def channels_cmd(client, message):
    user_id = message.from_user.id
    if is_owner(user_id):
        text = "\n".join([f"{n} → {u}" for n, u in CHANNELS.items()])
        await message.reply(text[:4000])
    else:
        buttons = [[InlineKeyboardButton(name, callback_data=f"rec|{name}")] for name in CHANNELS]
        await message.reply("📺 Select channel:", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^rec\|"))
async def channel_button(client, cq):
    name = cq.data.split("|")[1]
    url = CHANNELS.get(name)
    if url:
        await cq.answer(f"Recording started: {name}")
        # Recording function call
    else:
        await cq.answer("❌ Channel not found", show_alert=True)

@app.on_message(filters.command("Add_dost") & filters.user(OWNER_ID))
async def add_dost(client, message):
    try:
        new_id = int(message.command[1])
        if new_id not in dost_list:
            dost_list.append(new_id)
            await message.reply(f"✅ User {new_id} added to Dost list")
    except:
        await message.reply("Usage: /Add_dost <user_id>")

@app.on_message(filters.command("remove_dost") & filters.user(OWNER_ID))
async def remove_dost(client, message):
    try:
        remove_id = int(message.command[1])
        if remove_id in dost_list:
            dost_list.remove(remove_id)
            await message.reply(f"✅ User {remove_id} removed from Dost list")
    except:
        await message.reply("Usage: /remove_dost <user_id>")

@app.on_message(filters.command("dost_list"))
async def dost_list_cmd(client, message):
    text = "\n".join([str(i) for i in dost_list])
    await message.reply(f"📜 Dost List:\n{text}")

@app.on_message(filters.command("search"))
async def search_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: /search <keyword>")
    keyword = " ".join(message.command[1:]).lower()
    results = [n for n in CHANNELS if keyword in n.lower()]
    await message.reply("\n".join(results) if results else "No channels found")

# --- RUN ---
print("Bot running...")
app.run()
