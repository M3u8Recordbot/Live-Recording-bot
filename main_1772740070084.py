import asyncio
import os
import time
import subprocess
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ================= CONFIGURATION =================
API_ID = 29481626
API_HASH = "4892185769903521077c4cea97808b8c"
BOT_TOKEN = "8191916199:AAH66jt4Kzjgnh5GfROzCxHkTaHgtE34rM8"

TAG = "[ANIME CARTOON]"
DEFAULT_WM = "Anime-Cartoon.kesug.com"
GROUP_LINK = "https://t.me/+m_yCHi8Bdv02Y2Y1"
# =================================================

user_data = {}

app = Client(
    "RipperBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command(["dl", "ak"]))
async def start_proccess(client, message):
    uid = message.from_user.id
    cmd_text = message.text
    
    if "-c" not in cmd_text or "-n" not in cmd_text:
        return await message.reply("⚠️ **Format:** `/dl -c <link> -n <name>`")
    
    try:
        link = re.search(r"-c\s+(\S+)", cmd_text).group(1)
        name = re.search(r"-n\s+(.+)", cmd_text).group(1)
        user_data[uid] = {"link": link, "name": name, "res": "480", "pos": "tr", "bg": "yes"}
    except:
        return await message.reply("❌ Input invalid hai.")

    btns = InlineKeyboardMarkup([
        [InlineKeyboardButton("📺 480p", callback_data="res_480"), InlineKeyboardButton("🌟 720p", callback_data="res_720"), InlineKeyboardButton("💎 1080p", callback_data="res_1080")],
        [InlineKeyboardButton("🖼 Black BG: YES", callback_data="bg_yes"), InlineKeyboardButton("NO", callback_data="bg_no")],
        [InlineKeyboardButton("📍 WM: TOP-R", callback_data="wm_tr"), InlineKeyboardButton("📍 WM: MIDDLE", callback_data="wm_mid")],
        [InlineKeyboardButton("⚡ START RECORDING ⚡", callback_data="run")]
    ])
    
    await message.reply(f"🔥 **{TAG} Engine v2.0**\n\n**File:** `{name}`", reply_markup=btns)

@app.callback_query()
async def handle_buttons(client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data
    if data.startswith("res_"):
        user_data[uid]["res"] = data.split("_")[1]
        await query.answer(f"Quality: {user_data[uid]['res']}p")
    elif data == "run":
        await query.message.delete()
        await engine(client, query.message, uid)

async def engine(client, message, uid):
    s = user_data[uid]
    name, res = s['name'], s['res']
    status = await client.send_message(message.chat.id, "🛠 **Initializing Engine...**")
    
    for i in range(0, 101, 10):
        bar = "▰" * (i // 10) + "▱" * (10 - (i // 10))
        await status.edit(f"🎬 **{TAG} Recording**\n|{bar}| {i}%\n\n**Title:** `{name}`")
        await asyncio.sleep(24)

    output_name = f"{TAG} {name}_{res}p.mkv"
    pos_map = {"tr": "w-tw-10:10", "mid": "(w-tw)/2:(h-th)/2"}
    wm_pos = pos_map.get(s["pos"], "w-tw-10:10")
    bg_filter = f"scale={res}:-1,pad={res}:{res}:(ow-iw)/2:(oh-ih)/2:black," if s["bg"] == "yes" else ""

    await status.edit("⚙️ **FFmpeg Processing...**")
    
    cmd = f'ffmpeg -y -i "{s["link"]}" -t 00:59:00 -vf "{bg_filter}drawtext=text=\'{DEFAULT_WM}\':x={wm_pos}:fontsize=24:fontcolor=white@0.8" -c:v libx264 -preset ultrafast -metadata:s:a:0 title="{TAG} Hindi" "{output_name}"'
    
    process = await asyncio.create_subprocess_shell(cmd)
    await process.wait()

    await status.edit("🚀 **Uploading...**")
    await client.send_video(
        chat_id=message.chat.id,
        video=output_name,
        caption=f"✅ **Task Completed!**\n🎬 {TAG}",
        supports_streaming=True
    )
    
    if os.path.exists(output_name): os.remove(output_name)
    await status.delete()

app.run()
  
