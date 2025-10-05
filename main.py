from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp
import os
from flask import Flask
import threading
from dotenv import load_dotenv
import re

# Load .env file
load_dotenv()

# ====== BOT CONFIG =======
API_ID = "14050586"  # replace if needed
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
    thread.daemon = True
    thread.start()

# helper: sanitize filename
def sanitize_filename(s):
    s = s or "video"
    s = re.sub(r'[\\/*?:"<>|]', "", s)
    s = s.strip()
    if len(s) > 120:
        s = s[:120]
    return s

# ====== START COMMAND =======
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("Support", url="https://t.me/cutedevloper")],
        [InlineKeyboardButton("Update", url="https://t.me/cutedevlopers")]
    ])
    await message.reply(
        f"Hi {message.from_user.mention},\n\n"
        "**Send me any video URL from XMaster (or supported sites) to fetch and download it.**\n\n"
        "__Educational use only__",
        reply_markup=btn
    )

# ====== URL HANDLER =======
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_url(client, message):
    url = message.text.strip()

    if not url.startswith("http"):
        return await message.reply("Please send a valid video URL.")

    msg = await message.reply("Analyzing video...")

    try:
        # Use extract_info but do NOT rely on info['url'] for later download.
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'skip_download': True,
            # 'format': 'best'  # optional
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title") or "video"
        thumbnail = info.get("thumbnail", None)
        ext = info.get("ext") or "mp4"

        # store original page URL (not the ephemeral media url)
        download_data[str(message.from_user.id)] = {
            "page_url": url,
            "title": title,
            "ext": ext
        }

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Download Now", callback_data="download_video")]
        ])

        caption = f"**Title:** `{title}`\n**Type:** `{ext}`"

        if thumbnail:
            await msg.delete()
            await message.reply_photo(photo=thumbnail, caption=caption, reply_markup=button, has_spoiler=True)
        else:
            await msg.edit(caption, reply_markup=button)

    except Exception as e:
        await msg.edit(f"❌ Error while analyzing: `{e}`")

# ====== DOWNLOAD CALLBACK =======
@bot.on_callback_query(filters.regex("download_video"))
async def handle_download(client, callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = download_data.get(user_id)

    if not data:
        return await callback_query.message.reply("Session expired. Please send the URL again.")

    await callback_query.answer("Downloading...")

    try:
        original_page = data["page_url"]
        title = sanitize_filename(data.get("title"))
        ext = data.get("ext", "mp4")
        filename = f"{title}.{ext}"

        # ensure unique filename
        i = 1
        basefn = filename
        while os.path.exists(filename):
            filename = f"{title}_{i}.{ext}"
            i += 1

        ydl_opts = {
            'outtmpl': filename,
            'quiet': True,
            'noplaylist': True,
            'format': 'best',  # choose best available single-file format
            # if you have ffmpeg on server and want merged mp4: 'format': 'bestvideo+bestaudio/best', 'merge_output_format': 'mp4'
        }

        # Download using the original page URL so yt-dlp can re-extract valid media URLs.
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([original_page])

        # Try to send as video; fallback to document if it fails (size, or format)
        try:
            await callback_query.message.reply_video(
                video=filename,
                caption=f"**{title}**\nUploaded "
            )
        except Exception as send_exc:
            # fallback
            await callback_query.message.reply_document(
                document=filename,
                caption=f"**{title}**\n(Uploaded as document because video upload failed: {send_exc})"
            )

        # cleanup
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        await callback_query.message.reply(f"❌ Upload failed: `{e}`")

# ====== RUN BOT =======
keep_alive()
bot.run()