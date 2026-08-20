# -*- coding: utf-8 -*-

import os
import re
import logging
import sys
import tempfile
import subprocess
from io import BytesIO
from datetime import datetime, timedelta
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
import asyncio

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")  # Имена каналов через запятую (без @)
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # Секунд между проверками

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не настроен!")
if not SOURCE_CHANNELS:
    raise ValueError("❌ SOURCE_CHANNELS не настроен!")
if not TARGET_CHANNEL_ID:
    raise ValueError("❌ TARGET_CHANNEL_ID не настроен!")

# Парсим каналы
SOURCE_CHANNEL_LIST = [x.strip() for x in SOURCE_CHANNELS.split(',') if x.strip()]

# Стиль ЧП ВМ
TARGET_W = int(os.getenv("TARGET_W", "720"))
TARGET_H = int(os.getenv("TARGET_H", "900"))
CHP_GRADIENT_PCT = float(os.getenv("CHP_GRADIENT_PCT", "0.48"))
MN_TITLE_ZONE_PCT = float(os.getenv("MN_TITLE_ZONE_PCT", "0.23"))
BRIGHTNESS_FACTOR = float(os.getenv("BRIGHTNESS_FACTOR", "0.85"))
FONT_CHP = os.getenv("FONT_CHP", "Montserrat-Black.ttf")

# ==================== ЛОГИРОВАНИЕ ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Хранилище обработанных постов
processed_posts = set()

# ==================== ШРИФТЫ ====================

def download_fonts():
    fonts_urls = {
        "Montserrat-Black.ttf": "https://raw.githubusercontent.com/Dimaceo18/reporterbot/main/Montserrat-Black.ttf",
        "Arial.ttf": "https://github.com/matomo-org/travis-scripts/raw/master/fonts/Arial.ttf",
    }
    for font_name, url in fonts_urls.items():
        if not os.path.exists(font_name):
            try:
                logger.info(f"⬇️ Скачивание шрифта {font_name}...")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open(font_name, "wb") as f:
                        f.write(response.content)
                    logger.info(f"✅ Шрифт {font_name} скачан")
                else:
                    logger.warning(f"⚠️ Не удалось скачать {font_name}")
            except Exception as e:
                logger.error(f"❌ Ошибка скачивания {font_name}: {e}")

def load_font(font_name: str, size: int):
    try:
        if os.path.exists("Montserrat-Black.ttf"):
            return ImageFont.truetype("Montserrat-Black.ttf", size=size)
    except:
        pass
    
    try:
        if os.path.exists("Arial.ttf"):
            return ImageFont.truetype("Arial.ttf", size=size)
    except:
        pass
    
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
    ]
    
    for font_path in system_fonts:
        try:
            return ImageFont.truetype(font_path, size=size)
        except:
            pass
    
    return ImageFont.load_default()

# ==================== ОБРАБОТКА ИЗОБРАЖЕНИЙ ====================

def crop_to_ratio(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    w, h = img.size
    target_ratio = target_w / target_h
    cur_ratio = w / h
    
    if cur_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))

def apply_bottom_gradient(img: Image.Image, height_pct: float, max_alpha: int = 220) -> Image.Image:
    w, h = img.size
    gh = int(h * height_pct)
    if gh <= 0:
        return img
    
    overlay_alpha = Image.new("L", (w, h), 0)
    grad = Image.new("L", (1, gh), 0)
    for y in range(gh):
        a = int(max_alpha * (y / max(1, gh - 1)))
        grad.putpixel((0, y), a)
    grad = grad.resize((w, gh))
    overlay_alpha.paste(grad, (0, h - gh))
    
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    base = img.convert("RGBA")
    overlay = Image.composite(black, Image.new("RGBA", (w, h), (0, 0, 0, 0)), overlay_alpha)
    out = Image.alpha_composite(base, overlay)
    return out.convert("RGB")

def text_width(draw, s: str, font) -> int:
    try:
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]
    except:
        return len(s) * font.size // 2

def wrap_text(draw, text: str, font, max_width: int, max_lines: int = 6):
    words = text.split()
    if not words:
        return [""], True
    
    lines = []
    current = words[0]
    for word in words[1:]:
        test = current + " " + word
        if text_width(draw, test, font) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
            if len(lines) >= max_lines:
                return lines, False
    lines.append(current)
    return lines, True

def fit_text_block(draw, text: str, safe_w: int, max_block_h: int,
                   max_lines: int = 6, start_size: int = 90, min_size: int = 16):
    text = (text or "").strip()
    if not text:
        text = " "
    
    size = start_size
    while size >= min_size:
        font = load_font(FONT_CHP, size)
        lines, ok = wrap_text(draw, text, font, safe_w, max_lines=max_lines)
        spacing = int(size * 0.22)
        heights = []
        total_h = 0
        max_w = 0
        for ln in lines:
            try:
                bb = draw.textbbox((0, 0), ln, font=font)
                lw = bb[2] - bb[0]
                lh = bb[3] - bb[1]
            except:
                lw = len(ln) * size // 2
                lh = size
            heights.append(lh)
            total_h += lh
            max_w = max(max_w, lw)
        total_h += spacing * (len(lines) - 1)
        if ok and max_w <= safe_w and total_h <= max_block_h:
            return font, lines, heights, spacing, total_h
        size -= 2
    
    font = load_font(FONT_CHP, min_size)
    lines, _ = wrap_text(draw, text, font, safe_w, max_lines=max_lines)
    spacing = int(min_size * 0.22)
    heights = []
    total_h = 0
    for ln in lines:
        try:
            bb = draw.textbbox((0, 0), ln, font=font)
            lh = bb[3] - bb[1]
        except:
            lh = min_size
        heights.append(lh)
        total_h += lh
    total_h += spacing * (len(lines) - 1)
    return font, lines, heights, spacing, total_h

def clean_title_for_card(title: str) -> str:
    if not title:
        return ""
    
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\u2600-\u27BF"
        "]+",
        flags=re.UNICODE
    )
    clean = emoji_pattern.sub('', title)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def extract_title_from_text(text: str) -> str:
    if not text:
        return ""
    
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F700-\U0001F77F"
        "\U0001F780-\U0001F7FF"
        "\U0001F800-\U0001F8FF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\u2600-\u27BF"
        "]+",
        flags=re.UNICODE
    )
    clean_text = emoji_pattern.sub('', text).strip()
    
    if '\n' in clean_text:
        lines = clean_text.split('\n')
        title = lines[0].strip()
        if len(title) > 200:
            title = title[:197] + "..."
        return title
    
    if '. ' in clean_text and len(clean_text) > 100:
        parts = clean_text.split('. ', 1)
        title = (parts[0] + '.').strip()
        if len(title) > 200:
            title = title[:197] + "..."
        return title
    
    if len(clean_text) > 200:
        return clean_text[:197] + "..."
    return clean_text

def process_image(img: Image.Image, title_text: str) -> Image.Image:
    try:
        img = crop_to_ratio(img, TARGET_W, TARGET_H)
        img = img.resize((TARGET_W, TARGET_H), Image.Resampling.LANCZOS)
        img = ImageEnhance.Brightness(img).enhance(BRIGHTNESS_FACTOR)
        img = apply_bottom_gradient(img, height_pct=CHP_GRADIENT_PCT, max_alpha=220)
        
        draw = ImageDraw.Draw(img)
        margin_x = int(img.width * 0.06)
        margin_bottom = int(img.height * 0.08)
        safe_w = img.width - 2 * margin_x
        title_max_h = int(img.height * MN_TITLE_ZONE_PCT)
        
        clean_title = clean_title_for_card(title_text)
        text = (clean_title or "Без заголовка").strip().upper()
        
        font, lines, heights, spacing, total_h = fit_text_block(
            draw=draw, text=text, safe_w=safe_w,
            max_block_h=title_max_h, max_lines=6,
            start_size=int(img.height * 0.11), min_size=16
        )
        
        line_height = font.size
        total_text_height = len(lines) * line_height + (len(lines) - 1) * 2
        y = img.height - margin_bottom - total_text_height
        
        for ln in lines:
            draw.text((margin_x, y), ln, font=font, fill="white")
            y += line_height + 2
        
        return img
    except Exception as e:
        logger.error(f"❌ Ошибка обработки изображения: {e}")
        return img

def process_photo_bytes(photo_bytes: bytes, title_text: str) -> BytesIO:
    try:
        img = Image.open(BytesIO(photo_bytes)).convert("RGB")
        img = process_image(img, title_text)
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"❌ Ошибка обработки фото: {e}")
        return BytesIO(photo_bytes)

# ==================== ПАРСИНГ RSS ====================

def get_channel_posts(channel_name: str, limit: int = 10):
    """Получение постов из канала через RSS"""
    try:
        url = f"https://t.me/s/{channel_name}"
        logger.info(f"📡 Парсинг канала: {channel_name}")
        
        response = requests.get(url, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка доступа к каналу: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # Находим все посты
        for post in soup.find_all('div', class_='tgme_widget_message')[:limit]:
            try:
                # Текст поста
                text_elem = post.find('div', class_='tgme_widget_message_text')
                text = text_elem.get_text() if text_elem else ""
                
                # Дата
                date_elem = post.find('time', class_='tgme_widget_message_date')
                date_str = date_elem.get('datetime') if date_elem else None
                
                # Изображение
                img_elem = post.find('a', class_='tgme_widget_message_photo_wrap')
                img_url = None
                if img_elem and img_elem.get('style'):
                    style = img_elem.get('style')
                    match = re.search(r'background-image:url\(\'([^\']+)\'\)', style)
                    if match:
                        img_url = match.group(1)
                
                # Видео
                video_elem = post.find('video', class_='tgme_widget_message_video')
                video_url = None
                if video_elem:
                    video_url = video_elem.get('src')
                
                # Создаем уникальный ID поста
                post_id = hashlib.md5(f"{text}{date_str}".encode()).hexdigest()
                
                posts.append({
                    'id': post_id,
                    'text': text,
                    'date': date_str,
                    'image_url': img_url,
                    'video_url': video_url,
                    'channel': channel_name
                })
                
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга поста: {e}")
                continue
        
        logger.info(f"✅ Найдено {len(posts)} постов в канале {channel_name}")
        return posts
        
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга канала {channel_name}: {e}")
        return []

def download_image(url: str) -> Optional[bytes]:
    """Скачивание изображения"""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания изображения: {e}")
    return None

# ==================== ОСНОВНОЙ БОТ ====================

class RSSBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.target_chat = TARGET_CHANNEL_ID
        self.processed = set()
        
    async def check_channels(self):
        """Проверка всех каналов на новые посты"""
        logger.info("🔍 Проверка каналов...")
        
        for channel in SOURCE_CHANNEL_LIST:
            try:
                posts = get_channel_posts(channel, limit=5)
                
                for post in posts:
                    if post['id'] in self.processed:
                        continue
                    
                    logger.info(f"📨 Новый пост в канале {channel}")
                    
                    # Обрабатываем пост
                    await self.process_post(post)
                    
                    # Добавляем в обработанные
                    self.processed.add(post['id'])
                    
                # Очищаем старые ID (чтобы не переполнять память)
                if len(self.processed) > 1000:
                    self.processed = set(list(self.processed)[-500:])
                    
            except Exception as e:
                logger.error(f"❌ Ошибка проверки канала {channel}: {e}")
    
    async def process_post(self, post: dict):
        """Обработка поста"""
        try:
            text = post.get('text', '')
            title = extract_title_from_text(text)
            
            # Если есть изображение
            if post.get('image_url'):
                logger.info(f"📸 Обработка фото из поста")
                img_data = download_image(post['image_url'])
                if img_data:
                    processed = process_photo_bytes(img_data, title)
                    caption = text[:1024] if text else ""
                    
                    await self.bot.send_photo(
                        chat_id=self.target_chat,
                        photo=BytesIO(processed.getvalue()),
                        caption=caption,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Фото отправлено в канал")
                    return
            
            # Если только текст
            if text:
                logger.info(f"📝 Текстовый пост")
                await self.bot.send_message(
                    chat_id=self.target_chat,
                    text=text,
                    parse_mode="HTML"
                )
                logger.info(f"✅ Текст отправлен в канал")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки поста: {e}")

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 <b>Бот для репоста через RSS</b>\n\n"
        f"📢 Каналы-источники: {', '.join(SOURCE_CHANNEL_LIST)}\n"
        f"📢 Целевой канал: <code>{TARGET_CHANNEL_ID}</code>\n"
        f"⏱ Интервал проверки: {CHECK_INTERVAL}с\n\n"
        f"✅ <b>Бот работает!</b>",
        parse_mode="HTML"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 <b>Статистика</b>\n\n"
        f"📨 Обработано постов: {len(bot.processed)}\n"
        f"📢 Каналов: {len(SOURCE_CHANNEL_LIST)}\n"
        f"⏱ Интервал: {CHECK_INTERVAL}с\n"
        f"✅ Бот работает!",
        parse_mode="HTML"
    )

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительная проверка каналов"""
    await update.message.reply_text("🔍 Начинаю проверку каналов...")
    await bot.check_channels()
    await update.message.reply_text("✅ Проверка завершена!")

# ==================== ЗАПУСК ====================

async def main():
    global bot
    bot = RSSBot()
    
    logger.info("🚀 RSS Бот для репоста запускается...")
    logger.info(f"📊 Каналы: {SOURCE_CHANNEL_LIST}")
    logger.info(f"⏱ Интервал: {CHECK_INTERVAL}с")
    
    download_fonts()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("check", check_now))
    
    # Запускаем бота
    await app.initialize()
    await app.start()
    
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
        poll_interval=1.0
    )
    
    logger.info("🟢 Бот запущен!")
    
    # Основной цикл проверки
    while True:
        try:
            await bot.check_channels()
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле проверки: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)
