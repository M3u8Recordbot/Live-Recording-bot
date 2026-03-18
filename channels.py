# channels.py
import subprocess
from datetime import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ------------------------------
# CONFIG
# ------------------------------
BOT_TOKEN = "YOUR_BOT_TOKEN"
OWNER_ID = 5856009289
JIO_PLAYLIST_URL = "https://raw.githubusercontent.com/Sflex0719/ZioGarmTara/main/ZioGarmTara.m3u"

# ------------------------------
# CHANNELS (HIDDEN)
# ------------------------------
CHANNELS = {
    "Pogo Tata Play": "http://103.229.254.25:7001/play/a0dh/index.m3u8",
    "Pogo Jiotv": "http://103.180.212.191:3500/live/559.m3u8",
    "Sony Yay Tata Play": "http://103.229.254.25:7001/play/a0cl/index.m3u8",
    "Sony Yay Jiotv": "http://103.180.212.191:3500/live/872.m3u8",
    "Cartoon Network TPlay": "http://103.229.254.25:7001/play/a0cn/index.m3u8",
    "Cartoon Network Jiotv": "http://103.180.212.191:3500/live/166.m3u8",
    "Discovery Kids TPlay": "http://103.229.254.25:7001/play/a0dg/index.m3u8",
    "Discovery Kids Jiotv": "http://103.180.212.191:3500/live/554.m3u8",
    "Nick TPlay": "http://103.229.254.25:7001/play/a0cq/index.m3u8",
    "Nick Jiotv": "http://103.180.212.191:3500/live/545.m3u8",
    "Nick Jr TPlay": "http://103.229.254.25:7001/play/a0di/index.m3u8",
    "Nick Jr Jiotv": "http://103.180.212.191:3500/live/544.m3u8",
    "Sonic TPlay": "http://103.229.254.25:7001/play/a0dl/index.m3u8",
    "Sonic Jiotv": "http://103.180.212.191:3500/live/815.m3u8",
    "Disney Intl HD": "http://103.182.170.32:8888/play/a01y",
    "Disney Junior": "http://103.182.170.32:8888/play/a03q",
}

# ------------------------------
# LOAD JIOTV PLAYLIST
# ------------------------------
def load_jiotv_channels():
    try:
        r = requests.get(JIO_PLAYLIST_URL)
        lines = r.text.splitlines()
        temp_name = None

        for line in lines:
            if line.startswith("#EXTINF"):
                temp_name = line.split(",")[-1].strip()
            elif line.startswith("http") and temp_name:
                CHANNELS[temp_name + " (JioTV)"] = line
                temp_name = None

        print("✅ JioTV Loaded:", len(CHANNELS))

    except Exception as e:
        print("❌ Playlist error:", e)

# ------------------------------
# RECORD FUNCTION
# ------------------------------
async def start_record(url, duration):
    filename = f"rec_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    cmd = ["ffmpeg", "-y", "-i", url, "-t", duration, "-c:v", "libx264", "-c:a", "aac", filename]
    subprocess.run(cmd)
    return filename

# ------------------------------
# CHANNEL BUTTON UI
# ------------------------------
async def channels_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = []
    for name in list(CHANNELS.keys())[:50]:
        # Users/Admins never see URL
        buttons.append([InlineKeyboardButton(name, callback_data=f"rec|{name}")])

    await update.message.reply_text(
        "📺 Select Channel (Links Hidden)",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ------------------------------
# BUTTON CLICK
# ------------------------------
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    name = q.data.split("|")[1]
    url = CHANNELS.get(name)

    if not url:
        return await q.edit_message_text("❌ Channel not found")

    await q.edit_message_text(f"⏳ Recording started: {name}")
    await start_record(url, "00:10:00")  # default 10 min for demo

# ------------------------------
# /record COMMAND
# ------------------------------
async def record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        return await update.message.reply_text("/record <name/url> <time>")

    name = context.args[0]
    duration = context.args[1]

    url = CHANNELS.get(name, name)
    await update.message.reply_text(f"⏳ Recording: {name}")
    await start_record(url, duration)

# ------------------------------
# /search
# ------------------------------
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("/search <name>")

    q = " ".join(context.args).lower()
    res = [n for n in CHANNELS if q in n.lower()]
    if not res:
        await update.message.reply_text("❌ Not found")
    else:
        await update.message.reply_text("\n".join(res[:20]))

# ------------------------------
# OWNER ONLY LINK SHOW
# ------------------------------
async def owner_link_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Only Owner Allowed")

    msg = "\n".join([f"{k} → {v}" for k, v in CHANNELS.items()])
    await update.message.reply_text(msg[:4000])

# ------------------------------
# ADD / DELETE CHANNEL (OWNER ONLY)
# ------------------------------
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")

    name = context.args[0]
    url = context.args[1]
    CHANNELS[name] = url
    await update.message.reply_text(f"✅ Channel {name} added")

async def delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("❌ Owner only")

    name = context.args[0]
    CHANNELS.pop(name, None)
    await update.message.reply_text(f"✅ Channel {name} deleted")

# ------------------------------
# MAIN
# ------------------------------
def main():
    load_jiotv_channels()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("channels", channels_ui))
    app.add_handler(CommandHandler("record", record))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("ownerlinkshow", owner_link_show))
    app.add_handler(CommandHandler("add_channel", add_channel))
    app.add_handler(CommandHandler("delete_channel", delete_channel))
    app.add_handler(CallbackQueryHandler(button_click))

    print("🚀 Channels Bot Running (Secure Mode)...")
    app.run_polling()

if __name__ == "__main__":
    main()
