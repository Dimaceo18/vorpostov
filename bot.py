# -*- coding: utf-8 -*-

import subprocess
import sys
import os

# ==================== АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ====================

def install_dependencies():
    """Автоматическая установка всех зависимостей"""
    deps = [
        "telethon>=1.28.5",
        "Pillow==10.1.0",
        "moviepy==1.0.3",
        "requests==2.31.0",
        "numpy==1.26.0",
        "ffmpeg-python==0.2.0",
        "python-dotenv>=1.0.0"
    ]
    
    for dep in deps:
        try:
            # Проверяем, установлен ли пакет
            package_name = dep.split("==")[0].split(">=")[0].replace("-", "_")
            __import__(package_name)
            print(f"✅ {package_name} уже установлен")
        except ImportError:
            print(f"📦 Устанавливаем {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])

# Устанавливаем зависимости ПЕРЕД импортами
install_dependencies()

# ==================== ИМПОРТЫ ====================

import re
import logging
import asyncio
import tempfile
from io import BytesIO
from typing import Optional, List, Dict
from datetime import datetime
import traceback

import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telethon import TelegramClient, events, errors
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

try:
    from moviepy import VideoFileClip
except ImportError:
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
    except:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "moviepy==1.0.3"])
        from moviepy.video.io.VideoFileClip import VideoFileClip

# ==================== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================

# Для чтения каналов (UserBot)
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")

# Для публикации (Bot)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Каналы
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")  # ID или username через запятую
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")

# Проверка обязательных переменных
if not API_ID or not API_HASH:
    raise ValueError("❌ API_ID и API_HASH обязательны! Получите на my.telegram.org")
if not PHONE_NUMBER:
    raise ValueError("❌ PHONE_NUMBER не настроен! Номер телефона аккаунта")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не настроен! Получите у @BotFather")
if not SOURCE_CHANNELS:
    raise ValueError("❌ SOURCE_CHANNELS не настроен!")
if not TARGET_CHANNEL_ID:
    raise ValueError("❌ TARGET_CHANNEL_ID не настроен!")

# Парсим каналы-источники
SOURCE_CHANNEL_LIST = [x.strip() for x in SOURCE_CHANNELS.split(',') if x.strip()]

# Настройки оформления
TARGET_W = int(os.getenv("TARGET_W", "720"))
TARGET_H = int(os.getenv("TARGET_H", "900"))
CHP_GRADIENT_PCT = float(os.getenv("CHP_GRADIENT_PCT", "0.48"))
MN_TITLE_ZONE_PCT = float(os.getenv("MN_TITLE_ZONE_PCT", "0.23"))
BRIGHTNESS_FACTOR = float(os.getenv("BRIGHTNESS_FACTOR", "0.85"))
FONT_CHP = os.getenv("FONT_CHP", "Montserrat-Black.ttf")

# Настройки видео
VIDEO_BITRATE = os.getenv("VIDEO_BITRATE", "5000k")
VIDEO_PRESET = os.getenv("VIDEO_PRESET", "medium")
KEEP_ORIGINAL_AUDIO = os.getenv("KEEP_ORIGINAL_AUDIO", "true").lower() == "true"

# ==================== НАСТРОЙКА ЛОГИРОВАНИЯ ====================

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
    "last_post": None
}

# ==================== ШРИФТЫ ====================

def download_fonts():
    """Скачивание шрифтов"""
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
    """Загрузка шрифта с fallback"""
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
        
        if video.audio is not None and KEEP_ORIGINAL_AUDIO:
            try:
                processed_video = processed_video.set_audio(video.audio)
                logger.info(f"✅ Аудио сохранено")
            except Exception as e:
                logger.error(f"❌ Ошибка сохранения аудио: {e}")
        
        processed_video.write_videofile(
            temp_output,
            codec='libx264',
            audio_codec='aac',
            fps=video.fps,
            bitrate=VIDEO_BITRATE,
            threads=4,
            preset=VIDEO_PRESET,
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

# ==================== ОСНОВНОЙ КОД БОТА ====================

class RepostBot:
    def __init__(self):
        self.client = TelegramClient('session', API_ID, API_HASH)
        self.source_entities = []
        self.target_chat_id = TARGET_CHANNEL_ID
        
    async def start(self):
        """Запуск бота"""
        try:
            # Подключаемся к Telegram через UserBot
            await self.client.start(phone=PHONE_NUMBER)
            logger.info("✅ Подключение к Telegram установлено (UserBot)")
            
            me = await self.client.get_me()
            logger.info(f"👤 Аккаунт: {me.first_name} (@{me.username})")
            
            # Получаем сущности каналов-источников
            logger.info("🔍 Получаем информацию о каналах...")
            
            for channel in SOURCE_CHANNEL_LIST:
                try:
                    entity = await self.client.get_entity(channel)
                    self.source_entities.append(entity)
                    logger.info(f"✅ Канал-источник: {entity.title} (ID: {entity.id})")
                except Exception as e:
                    logger.error(f"❌ Ошибка доступа к каналу {channel}: {e}")
                    logger.info("💡 Убедитесь, что вы подписаны на канал")
                    return
            
            logger.info(f"🟢 Бот запущен! Отслеживается {len(self.source_entities)} каналов")
            logger.info(f"📤 Публикация будет в канал: {self.target_chat_id}")
            logger.info("💡 Для остановки нажмите Ctrl+C")
            
            # Регистрируем обработчики для каждого канала
            for entity in self.source_entities:
                @self.client.on(events.NewMessage(chats=entity))
                async def handler(event):
                    await self.handle_new_message(event)
            
            await self.client.run_until_disconnected()
            
        except errors.RPCError as e:
            logger.error(f"❌ Ошибка RPC: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            traceback.print_exc()
    
    async def handle_new_message(self, event):
        """Обработка нового сообщения"""
        try:
            message = event.message
            if not message:
                return
            
            if not message.text and not message.media:
                return
            
            text = message.text or message.caption or ""
            title = extract_title_from_text(text)
            
            logger.info(f"📨 Новый пост из канала {event.chat.title}")
            logger.info(f"📝 Заголовок: {title[:50] if title else 'нет'}")
            
            if message.photo:
                logger.info(f"📸 Обработка фото")
                try:
                    photo_data = await message.download_media(bytes)
                    if photo_data:
                        processed = process_photo_bytes(photo_data, title)
                        await self.send_photo_via_bot(processed, text)
                        stats['processed'] += 1
                        stats['last_post'] = f"Фото в {datetime.now().strftime('%H:%M:%S')}"
                        logger.info(f"✅ Фото отправлено в канал")
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки фото: {e}")
                return
            
            if message.video:
                logger.info(f"📹 Обработка видео")
                try:
                    video_data = await message.download_media(bytes)
                    if video_data:
                        processed = process_video_bytes(video_data, title)
                        await self.send_video_via_bot(processed, text)
                        stats['processed'] += 1
                        stats['last_post'] = f"Видео в {datetime.now().strftime('%H:%M:%S')}"
                        logger.info(f"✅ Видео отправлено в канал")
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки видео: {e}")
                return
            
            if text:
                logger.info(f"📝 Текстовый пост")
                await self.send_text_via_bot(text)
                stats['processed'] += 1
                stats['last_post'] = f"Текст в {datetime.now().strftime('%H:%M:%S')}"
                logger.info(f"✅ Текст отправлен в канал")
                
        except Exception as e:
            stats['errors'] += 1
            logger.error(f"❌ Ошибка обработки сообщения: {e}")

    async def send_photo_via_bot(self, photo_bytes: BytesIO, caption: str):
        """Отправка фото через Bot API"""
        import httpx
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('photo.png', photo_bytes, 'image/png')}
        data = {
            'chat_id': self.target_chat_id,
            'caption': caption[:1024] if caption else '',
            'parse_mode': 'HTML'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data)
            if response.status_code != 200:
                logger.error(f"❌ Ошибка отправки фото: {response.text}")

    async def send_video_via_bot(self, video_bytes: BytesIO, caption: str):
        """Отправка видео через Bot API"""
        import httpx
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        files = {'video': ('video.mp4', video_bytes, 'video/mp4')}
        data = {
            'chat_id': self.target_chat_id,
            'caption': caption[:1024] if caption else '',
            'parse_mode': 'HTML',
            'width': TARGET_W,
            'height': TARGET_H
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data)
            if response.status_code != 200:
                logger.error(f"❌ Ошибка отправки видео: {response.text}")

    async def send_text_via_bot(self, text: str):
        """Отправка текста через Bot API"""
        import httpx
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': self.target_chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            if response.status_code != 200:
                logger.error(f"❌ Ошибка отправки текста: {response.text}")

# ==================== ЗАПУСК ====================

async def main():
    logger.info("🚀 UserBot для репоста с оформлением ЧП ВМ запускается...")
    logger.info(f"📊 Количество каналов-источников: {len(SOURCE_CHANNEL_LIST)}")
    
    download_fonts()
    
    bot = RepostBot()
    await bot.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)
