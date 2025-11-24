import os
import re
import math
import threading
import asyncio
from pathlib import Path
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

# ========= ENV SETUP ========= #
load_dotenv()

API_ID = int(os.getenv("API_ID","14050586"))
API_HASH = os.getenv("API_HASH","42a60d9c657b106370c79bb0a8ac560c")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "5738579437"))
FORCE_CHANNEL_1 = os.getenv("FORCE_CHANNEL_1", "@CuteBotUpdate")
FORCE_CHANNEL_2 = os.getenv("FORCE_CHANNEL_2", "@SkyRexo")
DUMP_CHANNEL = int(os.getenv("DUMP_CHANNEL", "-1003328559256"))

# ========= BOT INIT ========= #
bot = Client("xmaster_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
app = Flask(__name__)

download_data = {}
BOT_USERNAME_CACHE = {"username": None}

# ========= FLASK KEEP ALIVE ========= #
@app.route("/")
def home():
    return "🔥 XMaster Downloader is Live!"

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    threading.Thread(target=run).start()


# ========= HELPERS ========= #
async def check_force_join(client, user_id):
    for ch in [FORCE_CHANNEL_1, FORCE_CHANNEL_2]:
        if not ch:
            continue
        try:
            m = await client.get_chat_member(ch, user_id)
            if m.status in ["banned", "kicked"]:
                return False
        except UserNotParticipant:
            return False
        except:
            pass
    return True

def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Join 1", url=f"https://t.me/{FORCE_CHANNEL_1.lstrip('@')}")],
        [InlineKeyboardButton("Join 2", url=f"https://t.me/{FORCE_CHANNEL_2.lstrip('@')}")],
        [InlineKeyboardButton("✔️ Joined", callback_data="refresh_join")]
    ])

def make_bar(p):
    p = max(0, min(p,100))
    return "["+"■"*(p//10)+"□"*(10-(p//10))+f"] {p}%"


# ========= FILENAME CLEANER ========= #
def clean_filename(text: str):
    return re.sub(r'[\\/*?:"<>|]', "_", text).strip().replace(" ", "_")


# ========= ANALYZE VIDEO ========= #
def analyze_url(url: str):
    opts = {
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "socket_timeout": 40,
        "retries": 10,
        "fragment_retries": 10,
        "http_headers": {"User-Agent": "Mozilla/5.0"}
    }
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)

    if not info:
        raise Exception("Invalid or unsupported link!")

    if "entries" in info:
        info = info["entries"][0]

    return {
        "title": info.get("title", "video"),
        "thumb": info.get("thumbnail"),
        "ext": info.get("ext", "mp4"),
    }


# ========= DOWNLOAD VIDEO ========= #
def download_video(url, fmt):
    Path("downloads").mkdir(exist_ok=True)

    opts = {
        "format": fmt,
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "quiet": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)

    if "entries" in info:
        info = info["entries"][0]

    title = clean_filename(info.get("title", "file"))
    ext = info.get("ext", "mp4")
    fpath = f"downloads/{title}.{ext}"

    if not Path(fpath).exists():
        raise Exception("File missing after download!")

    return fpath, title


# ========= PROGRESS UPLOAD ========= #
def upload_progress(current, total, message):
    try:
        p = int(current * 100 / total)
        if p % 5 != 0:
            return
        bar = make_bar(p)
        bot.loop.create_task(message.edit_text(f"📤 Uploading\n{bar}"))
    except:
        pass


# ========= /start ========= #
@bot.on_message(filters.command("start") & filters.private)
async def start(_, m):
    if len(m.command) > 1:  # File restore link
        try:
            return await m.reply_video(m.command[1])
        except:
            return

    if not await check_force_join(_, m.from_user.id):
        return await m.reply("Join First!", reply_markup=join_keyboard())

    await m.reply(
        f"👋 Hi {m.from_user.mention}\nSend any **video link** to download!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Support", url="https://t.me/cutedevloper")],
            [InlineKeyboardButton("Updates", url="https://t.me/cutedevlopers")]
        ])
    )


# ========= JOIN REFRESH ========= #
@bot.on_callback_query(filters.regex("^refresh_join$"))
async def fj(c,q):
    if not await check_force_join(c,q.from_user.id):
        return await q.answer("Join first",show_alert=True)
    await q.answer("Verified!",show_alert=True)
    await q.message.delete()


# ========= URL HANDLER ========= #
@bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def handle_url(c,m):
    url=m.text.strip()
    if not url.startswith("http"):
        return await m.reply("Send valid link!")

    if not await check_force_join(c,m.from_user.id):
        return await m.reply("Join First",reply_markup=join_keyboard())

    msg = await m.reply("🔍 Fetching info…")

    try:
        info = analyze_url(url)
        download_data[str(m.from_user.id)] = url
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("360p",callback_data="d360"),
             InlineKeyboardButton("480p",callback_data="d480")],
            [InlineKeyboardButton("720p",callback_data="d720"),
             InlineKeyboardButton("BEST",callback_data="dbest")]
        ])

        await msg.delete()

        if info["thumb"]:
            await m.reply_photo(info["thumb"],
                caption=f"🎬 **{info['title']}**\nSelect Quality👇",
                reply_markup=kb, has_spoiler=True)
        else:
            await m.reply(f"🎬 {info['title']}\nSelect👇",reply_markup=kb)

    except Exception as e:
        await msg.edit(f"❌ {e}")


# ========= DOWNLOAD + UPLOAD ========= #
@bot.on_callback_query(filters.regex("^d"))
async def down(c,q):
    await q.answer()
    uid=str(q.from_user.id)
    url=download_data.get(uid)

    if not url:
        return await q.message.reply("Send again")

    fmt=q.data[1:]
    quality = {
        "360":"best[height<=360]",
        "480":"best[height<=480]",
        "720":"best[height<=720]",
        "best":"best"
    }.get(fmt,"best")

    status=await q.message.reply("📥 Downloading…\n"+make_bar(0))

    loop=asyncio.get_running_loop()

    try:
        fpath,title = await loop.run_in_executor(None,download_video,url,quality)

        # Upload to dump always first
        upmsg = await c.send_video(DUMP_CHANNEL,fpath,caption=f"Stored: {title}")
        fid = upmsg.video.file_id

        # now send to user too
        await q.message.reply_video(fid,caption=f"Uploaded: **{title}**")

        # shareable link ready ✔
        if not BOT_USERNAME_CACHE["username"]:
            BOT_USERNAME_CACHE["username"]=(await c.get_me()).username

        link=f"https://t.me/{BOT_USERNAME_CACHE['username']}?start={fid}"
        await q.message.reply(f"🔗 Share Link:\n`{link}`")

        await status.edit("✅ Done!")

        try: os.remove(fpath)
        except: pass

    except Exception as e:
        await status.edit(str(e))


# ========= START BOT ========= #
keep_alive()
bot.run()