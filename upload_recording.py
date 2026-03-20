import os
import time
import asyncio
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- CONFIG ---
API_ID = "29481626"
API_HASH = "4892185769903521077c4cea97808b8c"
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 5856009289

# Database Substitute (Real project mein MongoDB use karein)
dost_list = [1900583882] # Pre-added dost
premium_users = {} # user_id: expiry_time
verified_users = {} # user_id: expiry_time
active_recordings = {} # user_id: count

app = Client("M3u8LiveRec", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPER FUNCTIONS ---
def is_owner(user_id):
    return user_id == OWNER_ID

def is_premium(user_id):
    if user_id in premium_users:
        return premium_users[user_id] > time.time()
    return False

def is_verified(user_id):
    if is_owner(user_id) or is_premium(user_id):
        return True
    if user_id in verified_users:
        return verified_users[user_id] > time.time()
    return False

# --- COMMANDS ---

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    text = (
        "👋 **Salaam**\n\n"
        f"👥 Abhi {len(dost_list)} Dost registered hain\n"
        "🔐 Verification: 🔴 OFF (Owner bypass)\n\n"
        "📋 **Commands:**\n"
        "• /record — M3U8 stream record karo\n"
        "• /plan — Subscription options\n"
        "• /Channels — Channel links dekho\n"
        "• /mera_id — Apna ID dekho"
    )
    await message.reply_text(text)

@app.on_message(filters.command("record"))
async def record_stream(client, message):
    user_id = message.from_user.id
    
    # Check Verification
    if not is_verified(user_id):
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔐 Verify Now", url="https://telegram.me/M3u8LiveRecordingBot?start=verify"),
            InlineKeyboardButton("How to verify?", url="https://t.me/+sG2rhAmwXEAzZDZl")
        ]])
        return await message.reply("🔐 **Verification Required**\n\nClick below to unlock access for 4 hours.", reply_markup=btn)

    # Check Limits
    limit = 5 if is_premium(user_id) else 4
    current_tasks = active_recordings.get(user_id, 0)
    
    if current_tasks >= limit:
        return await message.reply(f"❌ Limit reached! Max {limit} recordings allowed.")

    # Parse link and time
    try:
        args = message.command
        link = args[1]
        duration = args[2] if len(args) > 2 else "01:00:00"
        
        # Start Recording Logic (Placeholder for FFmpeg)
        active_recordings[user_id] = current_tasks + 1
        await message.reply(f"🔴 **Recording Started...**\n🔗 Link: `{link}`\n⏱ Duration: `{duration}`")
        
        # Simulation: Wait and then decrease count
        # In real bot, use subprocess to run FFmpeg
    except Exception:
        await message.reply("Format: `/record link duration` (e.g., `/record http://link.m3u8 01:30:00`)")

@app.on_message(filters.command("Add_dost") & filters.user(OWNER_ID))
async def add_dost(client, message):
    try:
        new_id = int(message.command[1])
        if new_id not in dost_list:
            dost_list.append(new_id)
            await message.reply(f"✅ User `{new_id}` added to Dost list.")
    except:
        await message.reply("Usage: `/Add_dost ID`")

@app.on_message(filters.command("plan"))
async def show_plan(client, message):
    plans = (
        "💎 **Premium Subscription**\n"
        "⏱ Time Limit: Up to 2 hours\n"
        "👤 Tasks: Up to 5\n\n"
        "💰 1 Week: $25\n"
        "💰 15 Days: $50\n"
        "💰 1 Month: $75\n\n"
        "Contact Owner for activation."
    )
    await message.reply_text(plans)

@app.on_message(filters.command("mera_id"))
async def my_id(client, message):
    await message.reply(f"🔹 Your ID: `{message.from_user.id}`")

# --- OWNER ONLY CONTROLS ---

@app.on_message(filters.command("unblock") & filters.user(OWNER_ID))
async def unblock_user(client, message):
    # Logic to remove user from block list
    await message.reply("✅ User unblocked successfully.")

print("Bot is started...")
app.run()
      
