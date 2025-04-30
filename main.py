from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import yt_dlp
import os
from flask import Flask
import threading

# ====== BOT CONFIG =======
API_ID = 123456  # Replace with your API ID
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"

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
        [InlineKeyboardButton("Support", url="https://t.me/YourSupportGroup")],
        [InlineKeyboardButton("Source", url="https://github.com/YourRepo")]
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
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'forceurl': True,
            'noplaylist': True,
            'simulate': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get("title")
            direct_url = info.get("url")
            thumbnail = info.get("thumbnail", None)
            ext = info.get("ext")

        download_data[str(message.from_user.id)] = {
            "url": direct_url,
            "title": title,
            "ext": ext
        }

        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Download Now", callback_data="download_video")]
        ])

        caption = f"**Title:** `{title}`\n**Type:** `{ext}`"

        if thumbnail:
            await msg.delete()
            await message.reply_photo(photo=thumbnail, caption=caption, reply_markup=button)
        else:
            await msg.edit(caption, reply_markup=button)

    except Exception as e:
        await msg.edit(f"❌ Error: `{e}`")

# ====== DOWNLOAD CALLBACK =======
@bot.on_callback_query(filters.regex("download_video"))
async def handle_download(client, callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = download_data.get(user_id)

    if not data:
        return await callback_query.message.reply("Session expired. Please send the URL again.")

    await callback_query.answer("Downloading...")

    try:
        filename = f"{data['title']}.{data['ext']}"
        ydl_opts = {
            'outtmpl': filename,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([data['url']])

        await callback_query.message.reply_video(
            video=filename,
            caption=f"**{data['title']}**\nUploaded by @YourBot"
        )

        os.remove(filename)
    except Exception as e:
        await callback_query.message.reply(f"❌ Upload failed: `{e}`")

# ====== RUN BOT =======
keep_alive()
bot.run()
