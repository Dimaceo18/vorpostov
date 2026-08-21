# -*- coding: utf-8 -*-

import os
import re
import logging
import sys
import tempfile
import subprocess
from io import BytesIO
from typing import Optional, List
import traceback
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import requests
from bs4 import BeautifulSoup
import feedparser
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# ==================== АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ====================

def install_dependencies():
    """Автоматическая установка всех зависимостей"""
    deps = [
        "python-telegram-bot==20.7",
        "Pillow==10.1.0",
        "moviepy==1.0.3",
        "requests==2.31.0",
        "numpy==1.26.0",
        "ffmpeg-python==0.2.0",
        "beautifulsoup4==4.12.2",
        "lxml==4.9.3",
        "feedparser==6.0.10"
    ]
    for dep in deps:
        try:
            package_name = dep.split("==")[0].replace("-", "_")
            __import__(package_name)
        except ImportError:
            print(f"📦 Устанавливаем {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep, "--user"])

install_dependencies()

# Добавляем пользовательские пути в sys.path
import site
site.addsitedir(os.path.expanduser("~/.local/lib/python3.10/site-packages"))

# ==================== ИМПОРТЫ ====================

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Bot, Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# Пробуем импортировать moviepy разными способами
try:
    from moviepy import VideoFileClip
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
    except ImportError:
        # Пробуем через sys.path
        import sys
        sys.path.append(os.path.expanduser("~/.local/lib/python3.10/site-packages"))
        try:
            from moviepy.video.io.VideoFileClip import VideoFileClip
        except ImportError:
            print("📦 Устанавливаем moviepy...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "moviepy==1.0.3", "--user"])
            from moviepy.video.io.VideoFileClip import VideoFileClip

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
RSS_FEED_URL = os.getenv("RSS_FEED_URL", "")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
MAX_POST_AGE_MINUTES = int(os.getenv("MAX_POST_AGE_MINUTES", "5"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не настроен!")
if not RSS_FEED_URL:
    raise ValueError("❌ RSS_FEED_URL не настроен!")
if not TARGET_CHANNEL_ID:
    raise ValueError("❌ TARGET_CHANNEL_ID не настроен!")

try:
    TARGET_CHANNEL_ID = int(TARGET_CHANNEL_ID)
except ValueError:
    raise ValueError("❌ TARGET_CHANNEL_ID должно быть числом!")

# Стиль ЧП ВМ
TARGET_W, TARGET_H = 720, 900
CHP_GRADIENT_PCT = 0.48
MN_TITLE_ZONE_PCT = 0.23
BRIGHTNESS_FACTOR = 0.85
FONT_CHP = "Montserrat-Black.ttf"
FONT_FALLBACK = "Arial.ttf"

# ==================== ЛОГИРОВАНИЕ ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Статистика
stats = {
    "started_at": datetime.now(),
    "processed": 0,
    "errors": 0,
    "last_post": None,
    "last_error": None
}

LAST_POSTS_FILE = "last_posts.json"

# ==================== РАБОТА С ПОСЛЕДНИМИ ПОСТАМИ ====================

def load_last_posts():
    try:
        if os.path.exists(LAST_POSTS_FILE):
            with open(LAST_POSTS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_last_posts(data):
    try:
        with open(LAST_POSTS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения: {e}")

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
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
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
    
    if '\n' in text:
        title = text.split('\n')[0].strip()
    else:
        title = text.strip()
    
    title = emoji_pattern.sub('', title)
    
    if len(title) > 200:
        title = title[:197] + "..."
    
    return title

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

# ==================== ОБРАБОТКА ВИДЕО ====================

def process_video_frame(frame: np.ndarray, title_text: str) -> np.ndarray:
    try:
        img = Image.fromarray(frame).convert("RGB")
        img = process_image(img, title_text)
        return np.array(img)
    except Exception as e:
        logger.error(f"❌ Ошибка обработки кадра: {e}")
        return frame

def process_video_bytes(video_bytes: bytes, title_text: str) -> BytesIO:
    temp_input = None
    temp_output = None
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(video_bytes)
            temp_input = f.name
        
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            temp_output = f.name
        
        logger.info(f"📹 Загрузка видео...")
        video = VideoFileClip(temp_input)
        logger.info(f"📹 Видео загружено: {video.duration}с")
        
        def process_frame(frame):
            return process_video_frame(frame, title_text)
        
        processed_video = video.fl_image(process_frame)
        
        if video.audio is not None:
            try:
                processed_video = processed_video.set_audio(video.audio)
                logger.info(f"✅ Оригинальное аудио сохранено")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения аудио: {e}")
        
        processed_video.write_videofile(
            temp_output,
            codec='libx264',
            audio_codec='aac',
            fps=video.fps,
            bitrate='5000k',
            threads=4,
            preset='medium',
            logger=None
        )
        
        video.close()
        processed_video.close()
        
        with open(temp_output, 'rb') as f:
            result_bytes = f.read()
        
        logger.info(f"✅ Видео обработано! Размер: {len(result_bytes) / (1024*1024):.2f} MB")
        
        output = BytesIO()
        output.write(result_bytes)
        output.seek(0)
        return output
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке видео: {e}")
        traceback.print_exc()
        output = BytesIO(video_bytes)
        output.seek(0)
        return output
    
    finally:
        try:
            if temp_input and os.path.exists(temp_input):
                os.unlink(temp_input)
            if temp_output and os.path.exists(temp_output):
                os.unlink(temp_output)
        except:
            pass

# ==================== RSS-ПАРСИНГ ====================

def get_rss_items():
    try:
        logger.info(f"📡 Запрос к RSS: {RSS_FEED_URL}")
        
        feed = feedparser.parse(RSS_FEED_URL)
        
        if feed.bozo:
            logger.error(f"⚠️ Ошибка парсинга RSS: {feed.bozo_exception}")
            return []
        
        if not feed.entries:
            logger.warning("⚠️ Нет постов в RSS")
            return []
        
        items = []
        for entry in feed.entries[:20]:
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            
            image_url = None
            if hasattr(entry, 'media_content'):
                for media in entry.media_content:
                    if media.get('type', '').startswith('image'):
                        image_url = media.get('url')
                        break
            
            if not image_url and hasattr(entry, 'description'):
                img_match = re.search(r'<img[^>]+src="([^"]+)"', entry.description)
                if img_match:
                    image_url = img_match.group(1)
            
            items.append({
                'id': hashlib.md5(entry.link.encode()).hexdigest(),
                'title': entry.title if hasattr(entry, 'title') else '',
                'description': entry.description if hasattr(entry, 'description') else '',
                'link': entry.link if hasattr(entry, 'link') else '',
                'pubDate': pub_date,
                'image_url': image_url,
                'channel': 'rss'
            })
        
        logger.info(f"📊 Получено {len(items)} постов")
        return items
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения RSS: {e}")
        return []

def download_image(url: str) -> Optional[bytes]:
    try:
        if not url:
            return None
        logger.info(f"📥 Скачивание фото...")
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            logger.info(f"✅ Фото скачано, размер: {len(response.content)} байт")
            return response.content
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания: {e}")
    return None

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - stats['started_at']
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    await update.message.reply_text(
        f"🤖 <b>Бот для репоста с оформлением ЧП ВМ (RSS)</b>\n\n"
        f"📡 RSS: <code>{RSS_FEED_URL}</code>\n"
        f"📢 Целевой канал: <code>{TARGET_CHANNEL_ID}</code>\n"
        f"📊 Обработано: {stats['processed']}\n"
        f"❌ Ошибок: {stats['errors']}\n"
        f"⏱ Работает: {hours}ч {minutes}м\n"
        f"⏳ Макс. возраст: {MAX_POST_AGE_MINUTES} мин\n\n"
        f"📌 <b>Как использовать:</b>\n"
        f"• Бот автоматически проверяет RSS-ленту\n"
        f"• На фото наносится заголовок (первая строка)\n"
        f"• Текст поста НЕ изменяется\n"
        f"• Команда /stats - статистика\n"
        f"• Команда /test - проверка подключения\n"
        f"• Команда /reset - сброс истории\n\n"
        f"✅ <b>Бот работает!</b>",
        parse_mode="HTML"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = datetime.now() - stats['started_at']
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    total = sum(len(v) for v in bot.last_posts.values())
    
    await update.message.reply_text(
        f"📊 <b>Статистика бота</b>\n\n"
        f"⏱ <b>Время работы:</b> {hours}ч {minutes}м\n"
        f"📨 <b>Обработано постов:</b> {stats['processed']}\n"
        f"❌ <b>Ошибок:</b> {stats['errors']}\n"
        f"📅 <b>Запущен:</b> {stats['started_at'].strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"📌 <b>Последний пост:</b> {stats['last_post'] or 'нет'}\n"
        f"📡 <b>RSS:</b> <code>{RSS_FEED_URL}</code>\n"
        f"📢 <b>Целевой канал:</b> <code>{TARGET_CHANNEL_ID}</code>\n"
        f"📊 <b>В истории:</b> {total} постов\n"
        f"🐍 <b>Python:</b> {sys.version.split()[0]}\n\n"
        f"✅ <b>Бот работает</b> 🟢",
        parse_mode="HTML"
    )

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bot_obj = context.bot
        
        try:
            target = await bot_obj.get_chat(TARGET_CHANNEL_ID)
            target_status = f"✅ {target.title} (ID: {TARGET_CHANNEL_ID})"
        except Exception as e:
            target_status = f"❌ Ошибка: {e}"
        
        me = await bot_obj.get_me()
        
        try:
            feed = feedparser.parse(RSS_FEED_URL)
            rss_status = f"✅ Работает, записей: {len(feed.entries)}"
            if feed.bozo:
                rss_status = f"⚠️ Ошибка парсинга: {feed.bozo_exception}"
        except Exception as e:
            rss_status = f"❌ Ошибка: {e}"
        
        await update.message.reply_text(
            f"🔍 <b>Проверка подключения</b>\n\n"
            f"🤖 <b>Бот:</b> @{me.username}\n"
            f"📡 <b>RSS:</b> {rss_status}\n"
            f"📢 <b>Целевой канал:</b> {target_status}\n"
            f"📊 <b>Обработано:</b> {stats['processed']}\n"
            f"❌ <b>Ошибок:</b> {stats['errors']}\n\n"
            f"🔄 <b>Статус:</b> {'✅ Все работает' if stats['processed'] > 0 else '⏳ Ожидание постов'}",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки: {e}")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot.last_posts = {}
    save_last_posts({})
    await update.message.reply_text("✅ История обработанных постов сброшена!")

# ==================== ОСНОВНОЙ БОТ ====================

class RSSBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.target_chat = TARGET_CHANNEL_ID
        self.last_posts = load_last_posts()
        self.running = True
        
    async def check_channels(self):
        logger.info("="*60)
        logger.info("🔍 ПРОВЕРКА RSS")
        logger.info("="*60)
        
        items = get_rss_items()
        
        if not items:
            logger.info("ℹ️ НЕТ ПОСТОВ В RSS")
            return
        
        new_posts = 0
        
        for item in items:
            try:
                post_id = item.get('id')
                channel = 'rss'
                
                pub_date = item.get('pubDate')
                if pub_date:
                    now = datetime.now(pub_date.tzinfo) if pub_date.tzinfo else datetime.now()
                    age_minutes = (now - pub_date).total_seconds() / 60
                    
                    if age_minutes > MAX_POST_AGE_MINUTES:
                        logger.info(f"⏭️ Пост старый ({age_minutes:.1f} мин) - пропускаем")
                        continue
                
                if post_id in self.last_posts.get(channel, []):
                    continue
                
                logger.info(f"✨ НОВЫЙ ПОСТ!")
                new_posts += 1
                
                await self.process_post(item, post_id)
                
                if channel not in self.last_posts:
                    self.last_posts[channel] = []
                self.last_posts[channel].append(post_id)
                
                if len(self.last_posts[channel]) > 50:
                    self.last_posts[channel] = self.last_posts[channel][-50:]
                
                save_last_posts(self.last_posts)
                logger.info(f"💾 Сохранено в историю")
                
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")
        
        logger.info("="*60)
        if new_posts == 0:
            logger.info("ℹ️ НОВЫХ ПОСТОВ НЕТ")
        else:
            logger.info(f"✅ ОБРАБОТАНО {new_posts} ПОСТОВ")
        logger.info("="*60)
    
    async def process_post(self, item, post_id):
        try:
            full_text = item.get('description') or item.get('title') or ""
            photo_title = extract_title_from_text(full_text)
            
            logger.info(f"🔄 ОБРАБОТКА:")
            logger.info(f"   📝 Текст (оригинал): {full_text[:150]}..." if len(full_text) > 150 else f"   📝 Текст (оригинал): {full_text}")
            logger.info(f"   🏷️ Заголовок для фото: {photo_title}")
            
            image_url = item.get('image_url')
            
            if image_url:
                logger.info("📸 Есть фото, обрабатываем...")
                img_data = download_image(image_url)
                if img_data:
                    processed = process_photo_bytes(img_data, photo_title)
                    
                    await self.bot.send_photo(
                        chat_id=self.target_chat,
                        photo=BytesIO(processed.getvalue()),
                        caption=full_text[:1024] if full_text else "",
                        parse_mode="HTML"
                    )
                    stats['processed'] += 1
                    stats['last_post'] = f"Фото в {datetime.now().strftime('%H:%M:%S')}"
                    logger.info("✅ ФОТО ОТПРАВЛЕНО!")
                    return
            
            if full_text:
                logger.info("📝 Только текст")
                await self.bot.send_message(
                    chat_id=self.target_chat,
                    text=full_text,
                    parse_mode="HTML"
                )
                stats['processed'] += 1
                stats['last_post'] = f"Текст в {datetime.now().strftime('%H:%M:%S')}"
                logger.info("✅ ТЕКСТ ОТПРАВЛЕН!")
                
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"❌ Ошибка обработки: {e}")
            traceback.print_exc()

# ==================== ЗАПУСК ====================

bot = None

async def main():
    global bot
    
    logger.info("🚀 Бот для репоста с оформлением ЧП ВМ (RSS) запускается...")
    logger.info(f"📡 RSS: {RSS_FEED_URL}")
    
    download_fonts()
    
    bot = RSSBot()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удалён")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления webhook: {e}")
    
    try:
        target = await app.bot.get_chat(TARGET_CHANNEL_ID)
        logger.info(f"✅ Целевой канал: {target.title} (ID: {TARGET_CHANNEL_ID})")
    except Exception as e:
        logger.error(f"❌ Ошибка доступа к целевому каналу: {e}")
        logger.info("💡 Убедитесь, что бот добавлен в канал как администратор")
        return
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("reset", reset))
    
    logger.info("✅ Обработчики зарегистрированы")
    logger.info(f"📊 Параметры оформления (ЧП ВМ):")
    logger.info(f"  • Размер: {TARGET_W}x{TARGET_H}")
    logger.info(f"  • Градиент: {int(CHP_GRADIENT_PCT*100)}%")
    logger.info(f"  • Затемнение: {int(BRIGHTNESS_FACTOR*100)}%")
    
    await app.initialize()
    await app.start()
    
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30
    )
    
    logger.info("🟢 Бот запущен!")
    logger.info("💡 Команды: /start, /stats, /test, /reset")
    
    while True:
        try:
            await bot.check_channels()
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        sys.exit(0)
