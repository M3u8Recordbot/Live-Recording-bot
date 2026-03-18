import time
import math
from pyrogram import Client, filters

# --- API Details (Yahan apni details bharein) ---
API_ID = 123456
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"

app = Client("ProgressBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Progress Bar and Data Helper ---
def get_progress_bar(current, total):
    percentage = current * 100 / total
    completed_blocks = int(percentage / 10)
    bar = "■" * completed_blocks + "□" * (10 - completed_blocks)
    return f"[{bar}] {percentage:.2f}%"

def human_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024

async def progress_handler(current, total, message, start_time, action_type="Uploading"):
    now = time.time()
    diff = now - start_time
    
    # Telegram rate limit se bachne ke liye har 4 second mein update
    if round(diff % 4.00) == 0 or current == total:
        speed = current / diff if diff > 0 else 0
        remaining_time = round((total - current) / speed) if speed > 0 else 0
        eta = time.strftime("%Hh %Mm %Ss", time.gmtime(remaining_time))
        
        # Aapke screenshot jaisa format
        text = (
            f"**{action_type}**\n"
            f"{get_progress_bar(current, total)}\n\n"
            f"➦ {human_size(current)} Of {human_size(total)}\n"
            f"➦ Speed : {human_size(speed)}/s\n"
            f"➦ Time Left : {eta}"
        )
        
        try:
            await message.edit_text(text)
        except:
            pass

# --- Command Handler ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Bot is Running! Send a file to test progress.")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    status_msg = await message.reply_text("`Starting Recording...`", quote=True)
    start_time = time.time()
    
    # 1. Recording/Downloading Stage
    file_path = await message.download(
        progress=progress_handler,
        progress_args=(status_msg, start_time, "Recording Video")
    )
    
    # 2. Uploading Stage
    await status_msg.edit_text("`Recording Done! Now Uploading...`")
    start_time_up = time.time()
    
    await client.send_video(
        chat_id=message.chat.id,
        video=file_path,
        caption="Success!",
        progress=progress_handler,
        progress_args=(status_msg, start_time_up, "Uploading")
    )
    
    await status_msg.delete()

app.run()
