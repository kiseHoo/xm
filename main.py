import os
import threading
import asyncio
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

# ================= ENV LOAD =================
load_dotenv()

API_ID = int(os.getenv("API_ID", "14050586"))
API_HASH = os.getenv("API_HASH", "42a60d9c657b106370c79bb0a8ac560c")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = int(os.getenv("OWNER_ID", "5738579437"))
FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "@CuteBotUpdate")
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "@SkyRexo")
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL", "-1003328559256"))


bot = Client(
    "xmaster_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

app = Flask(__name__)

DOWNLOAD_CACHE = {}
BOT_USERNAME = None

# ================= FLASK =================
@app.route("/")
def home():
    return "Bot is running"

def keep_alive():
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080)
    )
    t.daemon = True
    t.start()

# ================= FORCE JOIN =================
async def check_force_join(client, user_id):
    for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
        if not ch:
            continue
        try:
            await client.get_chat_member(ch, user_id)
        except UserNotParticipant:
            return False
        except Exception:
            pass
    return True

def force_join_keyboard():
    buttons = []
    if FORCE_CHANNEL_1:
        buttons.append([
            InlineKeyboardButton(
                "📢 Join Channel 1",
                url=f"https://t.me/{FORCE_CHANNEL_1.lstrip('@')}"
            )
        ])
    if FORCE_CHANNEL_2:
        buttons.append([
            InlineKeyboardButton(
                "📢 Join Channel 2",
                url=f"https://t.me/{FORCE_CHANNEL_2.lstrip('@')}"
            )
        ])
    buttons.append([
        InlineKeyboardButton("✅ I Joined", callback_data="refresh_join")
    ])
    return InlineKeyboardMarkup(buttons)

# ================= UTIL =================
def progress_bar(p):
    p = max(0, min(100, p))
    f = p // 10
    return f"[{'■'*f}{'□'*(10-f)}] {p}%"

# ================= DOWNLOAD =================
def yt_download(url, fmt):
    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 5,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    path = f"downloads/{info['title']}.mp4"
    return path, info["title"]

# ================= START =================
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    # Shareable link support
    if len(message.command) > 1:
        try:
            await message.reply_video(message.command[1])
        except Exception:
            await message.reply("❌ File expired or unavailable")
        return

    if not await check_force_join(client, message.from_user.id):
        return await message.reply(
            "🚫 Please join required channels first",
            reply_markup=force_join_keyboard()
        )

    await message.reply("👋 Send video URL to download")

# ================= REFRESH JOIN =================
@bot.on_callback_query(filters.regex("^refresh_join$"))
async def refresh_join(client, cq: CallbackQuery):
    if await check_force_join(client, cq.from_user.id):
        await cq.answer("✅ Verified", show_alert=True)
        await cq.message.delete()
    else:
        await cq.answer("❌ Join channels first", show_alert=True)

# ================= URL HANDLER =================
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def url_handler(client, message):
    url = message.text.strip()

    if not url.startswith("http"):
        return await message.reply("❌ Invalid URL")

    if not await check_force_join(client, message.from_user.id):
        return await message.reply(
            "🚫 Please join required channels",
            reply_markup=force_join_keyboard()
        )

    DOWNLOAD_CACHE[message.from_user.id] = url

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("360p", callback_data="dl_360"),
            InlineKeyboardButton("480p", callback_data="dl_480"),
        ],
        [
            InlineKeyboardButton("720p", callback_data="dl_720"),
            InlineKeyboardButton("BEST", callback_data="dl_best"),
        ],
    ])

    await message.reply("🎚 Choose quality", reply_markup=buttons)

# ================= DOWNLOAD CALLBACK =================
@bot.on_callback_query(filters.regex("^dl_"))
async def download_handler(client, cq: CallbackQuery):
    url = DOWNLOAD_CACHE.get(cq.from_user.id)
    if not url:
        return await cq.answer("Session expired", show_alert=True)

    fmt_map = {
        "dl_360": "best[height<=360]",
        "dl_480": "best[height<=480]",
        "dl_720": "best[height<=720]",
        "dl_best": "best",
    }

    fmt = fmt_map[cq.data]

    status = await cq.message.reply(
        "📥 Downloading...\n" + progress_bar(0)
    )

    loop = asyncio.get_running_loop()

    try:
        path, title = await loop.run_in_executor(
            None, yt_download, url, fmt
        )
    except Exception as e:
        return await status.edit(f"❌ Download failed:\n`{e}`")

    file_id = None

    # ===== DUMP CHANNEL (SAFE) =====
    if DUMP_CHANNEL != 0:
        try:
            dump_msg = await client.send_video(
                DUMP_CHANNEL,
                path,
                caption=title
            )
            if dump_msg.video:
                file_id = dump_msg.video.file_id
        except Exception as e:
            print("Dump failed:", e)

    # ===== SEND TO USER =====
    if file_id:
        await cq.message.reply_video(file_id, caption=f"✅ {title}")

        global BOT_USERNAME
        if not BOT_USERNAME:
            BOT_USERNAME = (await client.get_me()).username

        share_link = f"https://t.me/{BOT_USERNAME}?start={file_id}"
        await cq.message.reply(f"🔗 Share link:\n`{share_link}`")
    else:
        await cq.message.reply_video(path, caption=f"✅ {title}")

    try:
        os.remove(path)
    except Exception:
        pass

    await status.edit("✅ Done")

# ================= RUN =================
keep_alive()
bot.run()