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

# ====== ENV LOAD ======
load_dotenv()

# ====== BOT CONFIG =======
API_ID = int(os.getenv("API_ID", "14050586"))
API_HASH = os.getenv("API_HASH", "42a60d9c657b106370c79bb0a8ac560c")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Owner & channels (set these in .env)
OWNER_ID = int(os.getenv("OWNER_ID", "5738579437"))  # change if needed
FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1","@CuteBotUpdate")  # e.g. @YourChannel
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2","@CuteDevlopers")  # e.g. @YourSecondChannel
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL", "0"))    # e.g. -1001234567890

bot = Client("xmaster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

app = Flask(__name__)
download_data = {}  # store per-user URL/session
BOT_USERNAME_CACHE = {"username": None}

# ====== FLASK SERVER =======
@app.route("/")
def home():
    return "XMaster Downloader Bot is running!"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()


# ====== FORCE JOIN CHECK ======
async def check_force_join(client: Client, user_id: int):
    """Check if user joined required channels."""
    channels = [FORCE_CHANNEL_1, FORCE_CHANNEL_2]
    for ch in channels:
        if not ch:
            continue
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in ("banned", "kicked"):
                return False, ch
        except UserNotParticipant:
            return False, ch
        except Exception:
            # ignore invalid channel or other errors
            continue
    return True, None


def get_force_join_keyboard():
    btns = []
    if FORCE_CHANNEL_1:
        btns.append(
            [InlineKeyboardButton("📢 Join Channel 1", url=f"https://t.me/{FORCE_CHANNEL_1.lstrip('@')}")]
        )
    if FORCE_CHANNEL_2:
        btns.append(
            [InlineKeyboardButton("📢 Join Channel 2", url=f"https://t.me/{FORCE_CHANNEL_2.lstrip('@')}")]
        )
    btns.append([InlineKeyboardButton("✅ I Joined", callback_data="refresh_join")])
    return InlineKeyboardMarkup(btns)


# ====== ANALYZE FUNCTION =======
def analyze_url(url: str):
    """Get basic info (title, ext, thumbnail) using yt-dlp."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "geo_bypass": True,
        "ignoreerrors": False,
        "nocheckcertificate": True,
        "allow_unplayable_formats": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        # fallback: generic extractor
        ydl_opts["force_generic_extractor"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

    if not info:
        raise Exception("Failed to extract info from URL")

    return {
        "title": info.get("title", "Unknown"),
        "ext": info.get("ext", "mp4"),
        "thumbnail": info.get("thumbnail"),
    }


# ====== DOWNLOAD FUNCTION (SYNC, USED IN THREAD) =======
def safe_download(url: str, fmt: str, path: str = "downloads/"):
    os.makedirs(path, exist_ok=True)

    ydl_opts = {
        "outtmpl": f"{path}%(title)s.%(ext)s",
        "format": fmt,
        "noplaylist": True,
        "ignoreerrors": False,
        "geo_bypass": True,
        "quiet": True,
        "nocheckcertificate": True,
        "allow_unplayable_formats": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        print(f"⚠️ Normal download failed: {e}")
        ydl_opts["force_generic_extractor"] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

    if not info:
        raise Exception("Download failed, no info returned")

    title = info.get("title", "video")
    ext = info.get("ext", "mp4")
    file_path = f"{path}{title}.{ext}"
    return file_path, info


# ====== PROGRESS CALLBACK (UPLOAD) =======
def upload_progress(current, total, message):
    try:
        percent = int(current * 100 / total) if total else 0
        text = f"📤 Uploading... {percent}%"
        # schedule async edit on event loop
        if percent % 5 == 0:  # reduce spam
            bot.loop.create_task(message.edit_text(text))
    except Exception:
        pass


# ====== START COMMAND =======
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message):
    # /start <file_id> support (file-sharing link)
    if len(message.command) > 1:
        file_id = message.command[1]
        try:
            await message.reply_video(
                video=file_id,
                caption="🔁 Your requested file",
            )
        except Exception as e:
            await message.reply(f"❌ Failed to send file: `{e}`")
        return

    # Force join check
    ok, ch = await check_force_join(client, message.from_user.id)
    if not ok:
        await message.reply(
            "🚫 You must join the required channels to use this bot.",
            reply_markup=get_force_join_keyboard(),
        )
        return

    # Owner notification (simple)
    if OWNER_ID:
        try:
            await client.send_message(
                OWNER_ID,
                f"🆕 User started bot:\n"
                f"{message.from_user.mention} (`{message.from_user.id}`)",
            )
        except Exception:
            pass

    btn = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Support", url="https://t.me/cutedevloper")],
            [InlineKeyboardButton("Update", url="https://t.me/cutedevlopers")],
        ]
    )

    await message.reply(
        f"Hi {message.from_user.mention},\n\n"
        "📥 **Send me any supported video URL (XHamster, PH, etc.)**\n"
        "I will fetch details and let you choose quality.\n\n"
        "__For educational/demo use only.__",
        reply_markup=btn,
    )


# ====== FORCE JOIN REFRESH CALLBACK =======
@bot.on_callback_query(filters.regex("^refresh_join$"))
async def refresh_join(client: Client, callback_query: CallbackQuery):
    ok, ch = await check_force_join(client, callback_query.from_user.id)
    if not ok:
        await callback_query.answer(
            "❌ Please join all required channels first.", show_alert=True
        )
    else:
        await callback_query.answer("✅ You are verified!", show_alert=True)
        try:
            await callback_query.message.delete()
        except Exception:
            pass


# ====== URL HANDLER =======
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_url(client: Client, message):
    url = message.text.strip()

    # Force join check
    ok, ch = await check_force_join(client, message.from_user.id)
    if not ok:
        await message.reply(
            "🚫 You must join the required channels to use this bot.",
            reply_markup=get_force_join_keyboard(),
        )
        return

    if not url.startswith("http"):
        return await message.reply("❌ Please send a valid video URL.")

    msg = await message.reply("🔎 Analyzing video, please wait...")

    try:
        info = analyze_url(url)
        download_data[str(message.from_user.id)] = {"url": url}

        # quality buttons
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("360p", callback_data="download_360"),
                    InlineKeyboardButton("480p", callback_data="download_480"),
                ],
                [
                    InlineKeyboardButton("720p", callback_data="download_720"),
                    InlineKeyboardButton("Best", callback_data="download_best"),
                ],
            ]
        )

        caption = (
            f"**Title:** `{info['title']}`\n"
            f"**Type:** `{info['ext']}`\n\n"
            "__Choose your preferred quality to download:__"
        )

        await msg.delete()
        if info["thumbnail"]:
            await message.reply_photo(
                photo=info["thumbnail"],
                caption=caption,
                reply_markup=buttons,
                has_spoiler=True,
            )
        else:
            await message.reply(caption, reply_markup=buttons)

    except Exception as e:
        await msg.edit(f"❌ Error while analyzing: `{e}`")


# ====== DOWNLOAD CALLBACK (QUALITY SELECTION) =======
@bot.on_callback_query(filters.regex(r"^download_(360|480|720|best)$"))
async def handle_download(client: Client, callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = download_data.get(user_id)

    if not data:
        return await callback_query.message.reply(
            "⚠️ Session expired. Please send the URL again."
        )

    # Force join check
    ok, ch = await check_force_join(client, callback_query.from_user.id)
    if not ok:
        await callback_query.message.reply(
            "🚫 You must join the required channels to use this bot.",
            reply_markup=get_force_join_keyboard(),
        )
        return

    quality = callback_query.data.split("_", 1)[1]

    fmt_map = {
        "360": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        "480": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "720": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "best": "bestvideo+bestaudio/best",
    }

    fmt = fmt_map.get(quality, fmt_map["best"])
    url = data["url"]

    await callback_query.answer(f"⬇️ Downloading {quality}...", show_alert=False)
    status_msg = await callback_query.message.reply("⬇️ Downloading... Please wait.")

    loop = asyncio.get_running_loop()

    try:
        # Run blocking yt-dlp in thread
        file_path, info = await loop.run_in_executor(
            None, safe_download, url, fmt, "downloads/"
        )

        title = info.get("title", "Video")

        # Upload to dump channel first (storage)
        dump_msg = None
        if DUMP_CHANNEL != 0:
            try:
                dump_msg = await client.send_video(
                    chat_id=DUMP_CHANNEL,
                    video=file_path,
                    caption=f"📁 Stored: {title}",
                )
            except Exception as e:
                print(f"⚠️ Upload to dump channel failed: {e}")

        file_id = None
        if dump_msg and dump_msg.video:
            file_id = dump_msg.video.file_id

        # If no dump channel or failed, upload directly to user
        sent_to_user = None
        if file_id:
            sent_to_user = await callback_query.message.reply_video(
                video=file_id,
                caption=f"✅ **{title}**\nUploaded successfully!",
            )
        else:
            sent_to_user = await callback_query.message.reply_video(
                video=file_path,
                caption=f"✅ **{title}**\nUploaded successfully!",
                progress=upload_progress,
                progress_args=(status_msg,),
            )
            if sent_to_user and sent_to_user.video:
                file_id = sent_to_user.video.file_id

        # Shareable link via /start=<file_id>
        share_link = None
        if file_id:
            if not BOT_USERNAME_CACHE["username"]:
                me = await client.get_me()
                BOT_USERNAME_CACHE["username"] = me.username
            username = BOT_USERNAME_CACHE["username"]
            share_link = f"https://t.me/{username}?start={file_id}"

        try:
            await status_msg.delete()
        except Exception:
            pass

        # Delete local file to save space
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

        if share_link:
            await callback_query.message.reply(
                f"🔗 **Shareable Link:**\n`{share_link}`\n\n"
                "Anyone with this link can get the file via this bot."
            )

    except Exception as e:
        try:
            await status_msg.edit(f"❌ Download/Upload failed: `{e}`")
        except Exception:
            await callback_query.message.reply(f"❌ Download/Upload failed: `{e}`")


# ====== RUN BOT =======
keep_alive()
bot.run()