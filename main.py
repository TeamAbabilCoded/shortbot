import os
import asyncio
from pytube import YouTube
from moviepy.editor import VideoFileClip, CompositeVideoClip, VideoFileClip
from moviepy.video.fx.resize import resize
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import logging

# --- KONFIGURASI ---
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
CHANNEL_USERNAME = '@AutoShortYouTubeID'
WATERMARK_PATH = 'wm.gif'
CAPTION_FILE = 'caption.txt'
SHORT_DURATION = 60  # Durasi setiap klip
VERTICAL_RES = (720, 1280)  # Resolusi vertikal

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CEK JOIN CHANNEL ---
def is_user_in_channel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        member = context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

# --- START ---
def start(update: Update, context: CallbackContext):
    if not is_user_in_channel(update, context):
        keyboard = [[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "🔒 Anda belum bergabung ke channel kami, harap bergabung terlebih dahulu.",
            reply_markup=reply_markup
        )
        return

    update.message.reply_text("👋 Kirim link YouTube untuk saya potong menjadi Shorts!")

# --- HANDLE LINK ---
def handle_message(update: Update, context: CallbackContext):
    if not is_user_in_channel(update, context):
        keyboard = [[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "🔒 Anda belum bergabung ke channel kami, harap bergabung terlebih dahulu.",
            reply_markup=reply_markup
        )
        return

    url = update.message.text.strip()
    asyncio.run(process_video(update, context, url))

# --- DOWNLOAD VIDEO DENGAN PROGRESS ---
async def process_video(update, context, url):
    chat_id = update.effective_chat.id
    msg = context.bot.send_message(chat_id, "⬇️ Mulai download video...")

    try:
        yt = YouTube(url, on_progress_callback=lambda stream, chunk, bytes_remaining: on_progress(stream, chunk, bytes_remaining, msg, context))
        video = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        filename = yt.title.replace(" ", "_") + ".mp4"
        video.download(filename=filename)
    except Exception as e:
        msg.edit_text(f"Gagal download: {e}")
        return

    msg.edit_text("✅ Download selesai, mulai proses Shorts...")

    await asyncio.sleep(1)
    await generate_shorts(filename, chat_id, context)

    os.remove(filename)

# --- PROGRESS DOWNLOAD ---
def on_progress(stream, chunk, bytes_remaining, message, context):
    total = stream.filesize
    downloaded = total - bytes_remaining
    percent = int(downloaded / total * 100)
    try:
        context.bot.edit_message_text(chat_id=message.chat_id, message_id=message.message_id,
                                      text=f"⬇️ Download... {percent}%")
    except:
        pass

# --- POTONG VIDEO & KIRIM ---
async def generate_shorts(filename, chat_id, context):
    clip = VideoFileClip(filename)
    total_duration = int(clip.duration)
    num_clips = total_duration // SHORT_DURATION

    wm_clip = VideoFileClip(WATERMARK_PATH).resize(height=100)

    for i in range(num_clips):
        start = i * SHORT_DURATION
        end = start + SHORT_DURATION
        short_clip = clip.subclip(start, end).resize(height=VERTICAL_RES[1])

        # Tambahkan watermark
        wm_position = ("center", VERTICAL_RES[1] - 200)
        watermarked = CompositeVideoClip([short_clip, wm_clip.set_position(wm_position).set_duration(short_clip.duration)])

        output_name = f"short_{i}.mp4"
        watermarked.write_videofile(output_name, codec="libx264", audio_codec="aac", threads=4, logger=None)

        # Kirim video ke user
        with open("caption.txt", "r", encoding="utf-8") as f:
            caption = f.read()
        context.bot.send_video(chat_id, video=open(output_name, "rb"), caption=caption)

        os.remove(output_name)

    clip.close()

# --- MAIN ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
