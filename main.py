import os
import threading
import asyncio
import math
import yt_dlp

from dotenv import load_dotenv
from flask import Flask
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

# ================== ENV ==================
load_dotenv()

API_ID = int(os.getenv("API_ID", "14050586"))
API_HASH = os.getenv("API_HASH", "42a60d9c657b106370c79bb0a8ac560c")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Owner & channels (set these in .env OR use defaults here)
OWNER_ID = int(os.getenv("OWNER_ID", "5738579437"))  # change if needed
FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "@CuteBotUpdate")  # e.g. @YourChannel
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "@SkyRexo")        # e.g. @YourSecondChannel
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL", "-1003328559256"))   # e.g. -1001234567890


bot = Client(
    "xmaster_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

app = Flask(__name__)
download_data = {}
BOT_USERNAME_CACHE = {"username": None}

# ================== FLASK ==================
@app.route("/")
def home():
    return "XMaster Downloader Bot Running"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ================== FORCE JOIN ==================
async def check_force_join(client, user_id):
    for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
        if not ch:
            continue
        try:
            m = await client.get_chat_member(ch, user_id)
            if m.status in ("kicked", "banned"):
                return False, ch
        except UserNotParticipant:
            return False, ch
        except Exception:
            pass
    return True, None

def join_keyboard():
    btn = []
    if FORCE_CHANNEL_1:
        btn.append([InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{FORCE_CHANNEL_1.lstrip('@')}")])
    if FORCE_CHANNEL_2:
        btn.append([InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{FORCE_CHANNEL_2.lstrip('@')}")])
    btn.append([InlineKeyboardButton("✅ I Joined", callback_data="refresh_join")])
    return InlineKeyboardMarkup(btn)

# ================== PROGRESS BAR ==================
def bar(p):
    p = max(0, min(100, p))
    f = p // 10
    return f"[{'■'*f}{'□'*(10-f)}] {p}%"

# ================== ANALYZE ==================
def analyze_url(url):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "cookiesfrombrowser": ("chrome",),
        "extractor_args": {
            "xhamster": {"age": ["18"]}
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://xhamster.com/",
        },
        "retries": 5,
        "socket_timeout": 30,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise Exception("No video formats found")

    return {
        "title": info.get("title", "Unknown"),
        "thumbnail": info.get("thumbnail"),
    }

# ================== DOWNLOAD ==================
def safe_download(url, fmt, path="downloads/"):
    os.makedirs(path, exist_ok=True)

    ydl_opts = {
        "outtmpl": f"{path}%(title)s.%(ext)s",
        "format": fmt,
        "merge_output_format": "mp4",
        "cookiesfrombrowser": ("chrome",),
        "extractor_args": {
            "xhamster": {"age": ["18"]}
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://xhamster.com/",
        },
        "quiet": True,
        "retries": 5,
        "socket_timeout": 60,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    file = ydl.prepare_filename(info)
    return file, info

# ================== START ==================
@bot.on_message(filters.command("start") & filters.private)
async def start(_, m):
    if len(m.command) > 1:
        try:
            await m.reply_video(m.command[1])
        except Exception as e:
            await m.reply(str(e))
        return

    ok, _ = await check_force_join(bot, m.from_user.id)
    if not ok:
        return await m.reply("🚫 Join required channels first", reply_markup=join_keyboard())

    await m.reply(
        "👋 **Send any video URL** (XHamster supported)\n\n"
        "• Analyze\n• Choose quality\n• Download & Upload",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📢 Updates", url="https://t.me/cutedevlopers")],
                [InlineKeyboardButton("💬 Support", url="https://t.me/cutedevloper")],
            ]
        ),
    )

# ================== REFRESH JOIN ==================
@bot.on_callback_query(filters.regex("^refresh_join$"))
async def refresh(_, q: CallbackQuery):
    ok, _ = await check_force_join(bot, q.from_user.id)
    if ok:
        await q.answer("✅ Verified", show_alert=True)
        await q.message.delete()
    else:
        await q.answer("❌ Join all channels", show_alert=True)

# ================== URL HANDLER ==================
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def url_handler(_, m):
    url = m.text.strip()

    ok, _ = await check_force_join(bot, m.from_user.id)
    if not ok:
        return await m.reply("🚫 Join required channels first", reply_markup=join_keyboard())

    msg = await m.reply("🔎 Analyzing...")
    try:
        info = analyze_url(url)
        download_data[str(m.from_user.id)] = {"url": url}

        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("360p", callback_data="dl_360"),
                    InlineKeyboardButton("480p", callback_data="dl_480"),
                ],
                [
                    InlineKeyboardButton("720p", callback_data="dl_720"),
                    InlineKeyboardButton("BEST", callback_data="dl_best"),
                ],
            ]
        )

        await msg.delete()
        await m.reply_photo(
            info["thumbnail"],
            caption=f"🎬 **{info['title']}**\n\nChoose quality:",
            reply_markup=buttons,
            has_spoiler=True,
        )

    except Exception as e:
        await msg.edit(f"❌ {e}")

# ================== DOWNLOAD CALLBACK ==================
@bot.on_callback_query(filters.regex("^dl_"))
async def download_cb(_, q: CallbackQuery):
    user = str(q.from_user.id)
    if user not in download_data:
        return await q.answer("Session expired", show_alert=True)

    quality = q.data.split("_")[1]
    url = download_data[user]["url"]

    fmt_map = {
        "360": "best[height<=360]",
        "480": "best[height<=480]",
        "720": "best[height<=720]",
        "best": "best",
    }

    status = await q.message.reply(f"⬇️ Downloading...\n{bar(0)}")

    loop = asyncio.get_running_loop()
    try:
        file, info = await loop.run_in_executor(None, safe_download, url, fmt_map[quality])

        sent = None
        if DUMP_CHANNEL:
            sent = await bot.send_video(DUMP_CHANNEL, file)

        if sent and sent.video:
            await q.message.reply_video(sent.video.file_id)
        else:
            await q.message.reply_video(file)

        await status.edit("✅ Done")

        if os.path.exists(file):
            os.remove(file)

    except Exception as e:
        await status.edit(f"❌ {e}")

# ================== RUN ==================
keep_alive()
bot.run()