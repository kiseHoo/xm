import os
import threading
import asyncio
import yt_dlp
import math

from dotenv import load_dotenv
from flask import Flask
from pyrogram import Client, filters
from pyrogram.errors import UserNotParticipant
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ================= ENV =================
load_dotenv()

API_ID = int(os.getenv("API_ID", "14050586"))
API_HASH = os.getenv("API_HASH", "42a60d9c657b106370c79bb0a8ac560c")
BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = int(os.getenv("OWNER_ID", "5738579437"))
FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "@CuteBotUpdate")
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "@SkyRexo")
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL", "-1003328559256"))

bot = Client("xmaster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
app = Flask(__name__)

download_data = {}
BOT_USERNAME_CACHE = {"username": None}

# ================= FLASK =================
@app.route("/")
def home():
    return "Bot Running"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# ================= FORCE JOIN =================
async def check_force_join(client, user_id):
    for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
        if not ch:
            continue
        try:
            m = await client.get_chat_member(ch, user_id)
            if m.status in ("kicked", "banned"):
                return False
        except UserNotParticipant:
            return False
        except Exception:
            pass
    return True

def force_join_buttons():
    btn = []
    if FORCE_CHANNEL_1:
        btn.append([InlineKeyboardButton("📢 Join Channel 1",
                    url=f"https://t.me/{FORCE_CHANNEL_1.lstrip('@')}")])
    if FORCE_CHANNEL_2:
        btn.append([InlineKeyboardButton("📢 Join Channel 2",
                    url=f"https://t.me/{FORCE_CHANNEL_2.lstrip('@')}")])
    btn.append([InlineKeyboardButton("✅ I Joined", callback_data="refresh_join")])
    return InlineKeyboardMarkup(btn)

# ================= UTIL =================
def bar(p):
    p = max(0, min(100, p))
    f = p // 10
    return f"[{'■'*f}{'□'*(10-f)}] {p}%"

# ================= ANALYZE =================
def analyze(url):
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title": info.get("title", "Video"),
        "thumb": info.get("thumbnail")
    }

# ================= DOWNLOAD =================
def download(url, fmt):
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "format": fmt,
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
        "concurrent_fragment_downloads": 5,  # SPEED BOOST
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return f"downloads/{info['title']}.mp4", info["title"]

# ================= PROGRESS =================
def upload_progress(cur, total, msg):
    if not total:
        return
    p = int(cur * 100 / total)
    if p % 5 != 0:
        return
    async def edit():
        try:
            await msg.edit_text(f"📤 Uploading...\n{bar(p)}")
        except:
            pass
    bot.loop.create_task(edit())

# ================= START =================
@bot.on_message(filters.command("start") & filters.private)
async def start(client, m):
    if len(m.command) > 1:
        try:
            await m.reply_video(m.command[1])
        except:
            await m.reply("❌ File expired")
        return

    if not await check_force_join(client, m.from_user.id):
        return await m.reply("🚫 Join channels first", reply_markup=force_join_buttons())

    await m.reply("👋 Send video URL")

# ================= REFRESH =================
@bot.on_callback_query(filters.regex("refresh_join"))
async def refresh(client, cq):
    if await check_force_join(client, cq.from_user.id):
        await cq.answer("✅ Verified", show_alert=True)
        await cq.message.delete()
    else:
        await cq.answer("❌ Join first", show_alert=True)

# ================= URL =================
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def url_handler(client, m):
    if not await check_force_join(client, m.from_user.id):
        return await m.reply("🚫 Join channels", reply_markup=force_join_buttons())

    url = m.text.strip()
    msg = await m.reply("🔎 Analyzing...")

    info = analyze(url)
    download_data[str(m.from_user.id)] = url

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("360p", callback_data="d_360"),
         InlineKeyboardButton("480p", callback_data="d_480")],
        [InlineKeyboardButton("720p", callback_data="d_720"),
         InlineKeyboardButton("BEST", callback_data="d_best")]
    ])

    await msg.delete()
    await m.reply_photo(info["thumb"], caption=info["title"], reply_markup=btn, has_spoiler=True)

# ================= DOWNLOAD =================
@bot.on_callback_query(filters.regex("^d_"))
async def dl(client, cq):
    url = download_data.get(str(cq.from_user.id))
    if not url:
        return await cq.answer("Expired", show_alert=True)

    q = cq.data.split("_")[1]
    fmt = {
        "360": "best[height<=360]",
        "480": "best[height<=480]",
        "720": "best[height<=720]",
        "best": "best"
    }[q]

    status = await cq.message.reply("📥 Downloading...\n" + bar(0))
    loop = asyncio.get_running_loop()

    path, title = await loop.run_in_executor(None, download, url, fmt)

    # Upload to dump
    dump_msg = await client.send_video(DUMP_CHANNEL, path, caption=title)
    file_id = dump_msg.video.file_id

    # Send to user
    await cq.message.reply_video(
        file_id,
        caption=f"✅ {title}",
        progress=upload_progress,
        progress_args=(status,)
    )

    # Shareable link
    if not BOT_USERNAME_CACHE["username"]:
        BOT_USERNAME_CACHE["username"] = (await client.get_me()).username

    link = f"https://t.me/{BOT_USERNAME_CACHE['username']}?start={file_id}"
    await cq.message.reply(f"🔗 Share Link:\n`{link}`")

    os.remove(path)
    await status.edit("✅ Done")

# ================= RUN =================
keep_alive()
bot.run()