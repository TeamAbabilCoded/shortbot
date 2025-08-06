import os
import asyncio
import logging
import subprocess
from moviepy.editor import VideoFileClip, CompositeVideoClip
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from config import BOT_TOKEN, CHANNEL_USERNAME, WATERMARK_PATH, CAPTION_FILE, SHORT_DURATION, VERTICAL_RES

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_user_in_channel(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        member = context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

def start(update: Update, context: CallbackContext):
    if not is_user_in_channel(update, context):
        keyboard = [[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]]
        update.message.reply_text(
            "🔒 Anda belum bergabung ke channel kami, harap bergabung terlebih dahulu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    update.message.reply_text("👋 Kirim link YouTube untuk saya potong menjadi Shorts!")

def handle_message(update: Update, context: CallbackContext):
    if not is_user_in_channel(update, context):
        keyboard = [[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]]
        update.message.reply_text(
            "🔒 Anda belum bergabung ke channel kami, harap bergabung terlebih dahulu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    url = update.message.text.strip()
    asyncio.run(process_video(update, context, url))

async def process_video(update, context, url):
    chat_id = update.effective_chat.id
    msg = context.bot.send_message(chat_id, "⬇️ Mulai download video...")

    try:
        output_filename = "downloaded_video.mp4"
        command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "-o", output_filename,
            url
        ]
        subprocess.run(command, check=True)
    except Exception as e:
        msg.edit_text(f"Gagal download: {e}")
        return

    msg.edit_text("✅ Download selesai, mulai proses Shorts...")
    await asyncio.sleep(1)
    await generate_shorts(output_filename, chat_id, context)
    os.remove(output_filename)

async def generate_shorts(filename, chat_id, context):
    clip = VideoFileClip(filename)
    total_duration = int(clip.duration)
    num_clips = total_duration // SHORT_DURATION
    wm_clip = VideoFileClip(WATERMARK_PATH).resize(height=100)

    for i in range(num_clips):
        start = i * SHORT_DURATION
        end = start + SHORT_DURATION
        short_clip = clip.subclip(start, end).resize(height=VERTICAL_RES[1])
        wm_position = ("center", VERTICAL_RES[1] - 200)
        watermarked = CompositeVideoClip([short_clip, wm_clip.set_position(wm_position).set_duration(short_clip.duration)])
        output_name = f"short_{i}.mp4"
        watermarked.write_videofile(output_name, codec="libx264", audio_codec="aac", threads=4, logger=None)

        with open(CAPTION_FILE, "r", encoding="utf-8") as f:
            caption = f.read()
        context.bot.send_video(chat_id, video=open(output_name, "rb"), caption=caption)
        os.remove(output_name)

    clip.close()

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
