import os
import threading
import yt_dlp
from dotenv import load_dotenv
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Load env
load_dotenv()

# ====== BOT CONFIG =======
API_ID = 14050586
API_HASH = "42a60d9c657b106370c79bb0a8ac560c"
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Client("xmaster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
app = Flask(__name__)
download_data = {}

# ====== FLASK SERVER =======
@app.route('/')
def home():
    return "XMaster Downloader Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.start()

# ====== START COMMAND =======
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Support", url="https://t.me/cutedevloper")],
        [InlineKeyboardButton("Update", url="https://t.me/cutedevlopers")]
    ])
    await message.reply(
        f"Hi {message.from_user.mention},\n\n"
        "**Send me any video URL (XHamster, PH, etc.) to fetch and download it.**\n\n"
        "__Educational use only__",
        reply_markup=btn
    )

# ====== DOWNLOAD FUNCTION =======
def safe_download(url, path="downloads/"):
    os.makedirs(path, exist_ok=True)

    ydl_opts = {
        "outtmpl": f"{path}%(title)s.%(ext)s",
        "format": "best",
        "noplaylist": True,
        "ignoreerrors": True,
        "geo_bypass": True,
        "quiet": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Extractor failed")
            return f"{path}{info.get('title', 'video')}.{info.get('ext', 'mp4')}", info
    except Exception as e:
        print(f"⚠️ Normal extractor failed: {e}")
        ydl_opts["force_generic_extractor"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise Exception("Generic extractor failed too")
            return f"{path}{info.get('title', 'video')}.{info.get('ext', 'mp4')}", info

# ====== URL HANDLER =======
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_url(client, message):
    url = message.text.strip()

    if not url.startswith("http"):
        return await message.reply("❌ Please send a valid video URL.")

    msg = await message.reply("🔎 Analyzing video...")

    try:
        # Just get info without downloading
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "Unknown")
        ext = info.get("ext", "mp4")
        thumbnail = info.get("thumbnail")

        download_data[str(message.from_user.id)] = {"url": url}

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Download Now", callback_data="download_video")]
        ])

        caption = f"**Title:** `{title}`\n**Type:** `{ext}`"

        await msg.delete()
        if thumbnail:
            await message.reply_photo(
                photo=thumbnail,
                caption=caption,
                reply_markup=button,
                has_spoiler=True
            )
        else:
            await message.reply(caption, reply_markup=button)

    except Exception as e:
        await msg.edit(f"❌ Error while analyzing: `{e}`")

# ====== DOWNLOAD CALLBACK =======
@bot.on_callback_query(filters.regex("download_video"))
async def handle_download(client, callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = download_data.get(user_id)

    if not data:
        return await callback_query.message.reply("⚠️ Session expired. Please send the URL again.")

    url = data["url"]
    await callback_query.answer("⬇️ Downloading...")

    try:
        file_path, info = safe_download(url)

        await callback_query.message.reply_video(
            video=file_path,
            caption=f"✅ **{info.get('title','Video')}**\nUploaded successfully!"
        )

        os.remove(file_path)
    except Exception as e:
        await callback_query.message.reply(f"❌ Upload failed: `{e}`")

# ====== RUN BOT =======
keep_alive()
bot.run()