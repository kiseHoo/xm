import os
import threading
import asyncio
import yt_dlp

from dotenv import load_dotenv
from flask import Flask
from pyrogram import Client, filters
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

# 🔴 ADD YOUR DUMP CHANNEL
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


# ================= UTIL =================
def progress_bar(p):
    p = max(0, min(100, p))
    filled = p // 10
    return f"[{'■'*filled}{'□'*(10-filled)}] {p}%"


# ================= DOWNLOAD =================
def yt_download(url, fmt):

    os.makedirs("downloads", exist_ok=True)

    ydl_opts = {
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "geo_bypass_country": "US",
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 5,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", "video")
    ext = info.get("ext", "mp4")

    path = f"downloads/{title}.{ext}"

    if not os.path.exists(path):
        for file in os.listdir("downloads"):
            if file.startswith(title):
                path = f"downloads/{file}"
                break

    return path, title


# ================= START =================
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):

    if len(message.command) > 1:
        try:
            await message.reply_video(message.command[1])
        except Exception:
            await message.reply("❌ File expired or unavailable")
        return

    await message.reply(
        "👋 Send video URL\n\n"
        "You can send multiple links together."
    )


# ================= URL HANDLER =================
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def url_handler(client, message):

    urls = [u for u in message.text.split() if u.startswith("http")]

    if not urls:
        return await message.reply("❌ No valid URL found")

    for url in urls:

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

        await message.reply(
            f"🎚 Choose quality for:\n{url}",
            reply_markup=buttons
        )


# ================= DOWNLOAD CALLBACK =================
@bot.on_callback_query(filters.regex("^dl_"))
async def download_handler(client, cq: CallbackQuery):

    url = DOWNLOAD_CACHE.get(cq.from_user.id)

    if not url:
        return await cq.answer("Session expired", show_alert=True)

    fmt_map = {
        "dl_360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        "dl_480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "dl_720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "dl_best": "bestvideo+bestaudio/best",
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
        return await status.edit(
            "❌ Download Failed\n\n"
            f"`{e}`"
        )

    file_id = None

    # ===== SEND TO DUMP =====
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
    try:

        if file_id:
            await cq.message.reply_video(
                file_id,
                caption=f"✅ {title}"
            )
        else:
            sent = await cq.message.reply_video(
                path,
                caption=f"✅ {title}"
            )
            file_id = sent.video.file_id

        global BOT_USERNAME

        if not BOT_USERNAME:
            BOT_USERNAME = (await client.get_me()).username

        share_link = f"https://t.me/{BOT_USERNAME}?start={file_id}"

        await cq.message.reply(
            f"🔗 Share link:\n`{share_link}`"
        )

    except Exception as e:

        await cq.message.reply(
            f"❌ Upload failed\n`{e}`"
        )

    try:
        os.remove(path)
    except Exception:
        pass

    await status.edit("✅ Done")


# ================= RUN =================
keep_alive()
bot.run()