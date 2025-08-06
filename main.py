import os
import logging
import subprocess
import re
import tempfile
from datetime import datetime
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
    if not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be)/', url):
        update.message.reply_text("❌ Link tidak valid. Kirim link video YouTube yang benar.")
        return

    context.bot.send_chat_action(update.effective_chat.id, 'typing')
    context.application.create_task(process_video(update, context, url))

async def process_video(update, context, url):
    chat_id = update.effective_chat.id
    message = await context.bot.send_message(chat_id, "⬇️ Sedang mendownload video...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"video_{timestamp}.mp4"

    try:
        command = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            "-o", output_filename,
            url
        ]
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        await message.edit_text(f"❌ Gagal download video.")
        return

    await message.edit_text("✅ Download selesai. Proses menjadi Shorts...")
    try:
        await generate_shorts(output_filename, chat_id, context)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Gagal proses video: {e}")
    finally:
        if os.path.exists(output_filename):
            os.remove(output_filename)

async def generate_shorts(filename, chat_id, context):
    clip = VideoFileClip(filename)
    total_duration = int(clip.duration)
    num_clips = max(1, total_duration // SHORT_DURATION)
    wm_clip = VideoFileClip(WATERMARK_PATH).resize(height=100).loop()

    for i in range(num_clips):
        start = i * SHORT_DURATION
        end = start + SHORT_DURATION
        short_clip = clip.subclip(start, min(end, total_duration)).resize(height=VERTICAL_RES[1])
        wm_position = ("center", VERTICAL_RES[1] - 200)

        watermarked = CompositeVideoClip([
            short_clip,
            wm_clip.set_position(wm_position).set_duration(short_clip.duration)
        ])

        output_name = f"short_{i}_{datetime.now().strftime('%H%M%S')}.mp4"
        watermarked.write_videofile(output_name, codec="libx264", audio_codec="aac", threads=4, logger=None)

        with open(CAPTION_FILE, "r", encoding="utf-8") as f:
            caption = f.read()

        with open(output_name, "rb") as video_file:
            context.bot.send_chat_action(chat_id, 'upload_video')
            context.bot.send_video(chat_id, video=video_file, caption=caption)

        os.remove(output_name)
        short_clip.close()
        watermarked.close()

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
