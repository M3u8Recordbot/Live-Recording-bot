# LittleSingham Telegram Bot

## Overview
A full-featured Telegram bot built with Pyrogram for recording M3U8 streams, downloading OTT content, and managing users. Uses FFmpeg for video processing and yt-dlp for OTT downloads.

## Project Structure
- `main.py` — Main bot logic, all command handlers and recording coroutines
- `Config.py` — All configuration: tokens, owner IDs, channel links, limits
- `storage.py` — Persistent JSON storage for dosts, premium subscriptions, cookies
- `data.json` — Auto-created runtime data store
- `cookies.txt` — Auto-created when cookies are set
- `requirements.txt` — Python dependencies

## Tech Stack
- **Language**: Python 3.12
- **Telegram Library**: Pyrogram
- **Video Processing**: FFmpeg (system dependency)
- **Downloader**: yt-dlp
- **Storage**: JSON file (data.json)

## Workflow
- **Start application**: `python3 main.py` (webview — port 5000)
  - Runs the Pyrogram Telegram bot
  - Runs Flask admin panel on port 5000 (background thread)

## Web Admin Panel (port 5000)
- **Login**: password is `admin123` (change via `ADMIN_PASSWORD` env var)
- **Dashboard**: overview stats (dosts, premium, channels)
- **Dosts**: add by User ID + name, remove, view all
- **Premium**: activate plans (7/15/30/90/365 days), remove, view expiry
- **Channels**: view all default + custom channels, add new (key, name, emoji, TPlay URL, JioTV URL), remove custom ones

## Bot Commands
| Command | Description |
|---|---|
| `/start` | Welcome message with dost count + command list |
| `/record <url\|channel> <HH:MM:SS>` | Record M3U8 stream (direct URL or channel name) |
| `/Channels` | Browse predefined channels (Pogo, Nick, CN, etc.) |
| `/download_OTT <url>` | Download OTT content via yt-dlp |
| `/compress` | Re-encode a video to smaller size |
| `/set_cookies` | Set Netscape cookies for OTT access (Owner only) |
| `/cookies_status` | Check if cookies are set |
| `/del_cookies` | Delete cookies (Owner only) |
| `/Add_dost` | Add a user as Dost (Owner only) |
| `/dost_list` | List all Dosts |
| `/remove_dost <id>` | Remove a Dost (Owner only) |
| `/mera_id` | Show your profile (ID, plan, role) |
| `/statusme` | Check active recordings with cancel buttons |
| `/cancelme` / `/stop` | Cancel all your recordings |
| `/plan` | Show premium subscription info |
| `/add_premium <id> <days>` | Grant premium (Owner only) |
| `/user_unblock <id>` | Unblock a user (Owner only) |
| `/block_list` | List blocked users (Owner only) |
| `/user_dost_cancel <id>` | Cancel all recordings of a user (Owner only) |

## Predefined Channels (/Channels command)
- Pogo (TPlay + JioTV)
- Sony Yay (TPlay + JioTV)
- Cartoon Network (TPlay + JioTV)
- Discovery Kids (TPlay + JioTV)
- Nick (TPlay + JioTV)
- Nick Jr (TPlay + JioTV)
- Sonic (TPlay + JioTV)

## Recording Features
- Quality: 360p / 480p / 720p / 1080p / Best
- Aspect Ratio: Original / 16:9 / 4:3 / Black Bars
- Audio Tracks: Telugu / Hindi / Tamil / Malayalam / Kannada / Bengali / Marathi / Odia / English / All Tracks
- Real-time progress: dots progress bar, size, speed, ETA
- File naming: `LittleSinghamChannel.[DD-MM-YYYY].[HH:MM:SS AM].RESOp.[Lang].MP32.0.128K.H264.mp4`

## Spam/Block System
- Max 4 concurrent recordings per user
- 3 warnings before 1-hour block
- Owner is exempt from all limits

## User Levels
- **Owner**: Full access (IDs: 969084369, 5856009289)
- **Auth Users**: Trusted users, no verification needed
- **Dost**: Friends registered in the bot
- **Free User**: Default, max 2hr recordings, max 4 concurrent
