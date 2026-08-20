# -*- coding: utf-8 -*-

import os
import re
import logging
import sys
from io import BytesIO
from datetime import datetime
import hashlib
import json
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import signal

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не настроен!")
if not SOURCE_CHANNELS:
    raise ValueError("❌ SOURCE_CHANNELS не настроен!")
if not TARGET_CHANNEL_ID:
    raise ValueError("❌ TARGET_CHANNEL_ID не настроен!")

SOURCE_CHANNEL_LIST = [x.strip() for x in SOURCE_CHANNELS.split(',') if x.strip()]

# Стиль ЧП ВМ
TARGET_W = int(os.getenv("TARGET_W", "720"))
TARGET_H = int(os.getenv("TARGET_H", "900"))
CHP_GRADIENT_PCT = float(os.getenv("CHP_GRADIENT_PCT", "0.48"))
MN_TITLE_ZONE_PCT = float(os.getenv("MN_TITLE_ZONE_PCT", "0.23"))
BRIGHTNESS_FACTOR = float(os.getenv("BRIGHTNESS_FACTOR", "0.85"))

# ==================== ЛОГИРОВАНИЕ ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
                logger.info(f"⬇️ Скачивание {font_name}...")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open(font_name, "wb") as f:
                        f.write(response.content)
                    logger.info(f"✅ {font_name} скачан")
            except Exception as e:
                logger.error(f"❌ Ошибка скачивания {font_name}: {e}")

def load_font(size: int):
    fonts = [
        "Montserrat-Black.ttf",
        "Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for font_path in fonts:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size=size)
        except:
            pass
    return ImageFont.load_default()

# ==================== ОБРАБОТКА ИЗОБРАЖЕНИЙ ====================

def crop_to_ratio(img, target_w, target_h):
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

def apply_bottom_gradient(img, height_pct, max_alpha=220):
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

def text_width(draw, s, font):
    try:
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]
    except:
        return len(s) * font.size // 2

def wrap_text(draw, text, font, max_width, max_lines=6):
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

def fit_text_block(draw, text, safe_w, max_block_h, max_lines=6, start_size=90, min_size=16):
    text = (text or "").strip()
    if not text:
        text = " "
    
    size = start_size
    while size >= min_size:
        font = load_font(size)
        lines, ok = wrap_text(draw, text, font, safe_w, max_lines=max_lines)
        spacing = int(size * 0.22)
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
            total_h += lh
            max_w = max(max_w, lw)
        total_h += spacing * (len(lines) - 1)
        if ok and max_w <= safe_w and total_h <= max_block_h:
            return font, lines, spacing, total_h
        size -= 2
    
    font = load_font(min_size)
    lines, _ = wrap_text(draw, text, font, safe_w, max_lines=max_lines)
    spacing = int(min_size * 0.22)
    total_h = len(lines) * min_size + (len(lines) - 1) * spacing
    return font, lines, spacing, total_h

def clean_title(title):
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

def extract_title(text):
    if not text:
        return ""
    if '\n' in text:
        title = text.split('\n')[0]
    else:
        title = text[:200]
    return clean_title(title)

def process_image(img, title_text):
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
        
        text = (title_text or "Без заголовка").strip().upper()
        
        font, lines, spacing, total_h = fit_text_block(
            draw=draw, text=text, safe_w=safe_w,
            max_block_h=title_max_h, max_lines=6,
            start_size=int(img.height * 0.11), min_size=16
        )
        
        line_height = font.size
        y = img.height - margin_bottom - total_h
        
        for ln in lines:
            draw.text((margin_x, y), ln, font=font, fill="white")
            y += line_height + spacing
        
        return img
    except Exception as e:
        logger.error(f"❌ Ошибка обработки: {e}")
        return img

def process_photo_bytes(photo_bytes, title_text):
    try:
        img = Image.open(BytesIO(photo_bytes)).convert("RGB")
        img = process_image(img, title_text)
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return BytesIO(photo_bytes)

# ==================== ПАРСИНГ КАНАЛА ====================

def get_latest_post(channel_name):
    """Получение ТОЛЬКО ПОСЛЕДНЕГО поста с детальным логированием"""
    try:
        url = f"https://t.me/s/{channel_name}"
        logger.info(f"📡 Парсинг {channel_name}...")
        
        response = requests.get(url, timeout=30)
        response.encoding = 'utf-8'
        
        if response.status_code != 200:
            logger.error(f"❌ Ошибка: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        all_posts = soup.find_all('div', class_='tgme_widget_message')
        
        if not all_posts:
            logger.warning(f"⚠️ Постов не найдено в {channel_name}")
            return None
        
        logger.info(f"📊 Всего найдено постов: {len(all_posts)}")
        
        # Показываем последние 5 постов
        logger.info("📋 Последние 5 постов в канале:")
        for i, p in enumerate(all_posts[:5]):
            try:
                text_elem = p.find('div', class_='tgme_widget_message_text')
                text = text_elem.get_text()[:50] if text_elem else "(без текста)"
                
                date_elem = p.find('time', class_='tgme_widget_message_date')
                date_str = date_elem.get('datetime') if date_elem else None
                
                if not date_str:
                    time_tag = p.find('time')
                    if time_tag and time_tag.get('datetime'):
                        date_str = time_tag.get('datetime')
                    elif time_tag and time_tag.get('data-datetime'):
                        date_str = time_tag.get('data-datetime')
                
                logger.info(f"  [{i+1}] {date_str or 'нет даты'}: {text}...")
            except:
                logger.info(f"  [{i+1}] (ошибка)")
        
        # Берем ПЕРВЫЙ пост (самый свежий)
        post = all_posts[0]
        
        try:
            text_elem = post.find('div', class_='tgme_widget_message_text')
            text = text_elem.get_text() if text_elem else ""
            
            # Улучшенный парсинг даты
            date_str = None
            date_elem = post.find('time', class_='tgme_widget_message_date')
            if date_elem:
                date_str = date_elem.get('datetime')
            
            if not date_str:
                time_tags = post.find_all('time')
                for t in time_tags:
                    if t.get('datetime'):
                        date_str = t.get('datetime')
                        break
                    elif t.get('data-datetime'):
                        date_str = t.get('data-datetime')
                        break
            
            # Изображение
            img_elem = post.find('a', class_='tgme_widget_message_photo_wrap')
            img_url = None
            if img_elem and img_elem.get('style'):
                style = img_elem.get('style')
                match = re.search(r'background-image:url\(\'([^\']+)\'\)', style)
                if match:
                    img_url = match.group(1)
            
            if not img_url:
                img_tag = post.find('img', class_='tgme_widget_message_photo')
                if img_tag and img_tag.get('src'):
                    img_url = img_tag.get('src')
            
            post_id = hashlib.md5(f"{text}{date_str}".encode()).hexdigest()
            
            logger.info(f"🎯 ВЫБРАН пост для обработки:")
            logger.info(f"   📅 Дата: {date_str or 'не найдена'}")
            logger.info(f"   📝 Текст (первые 100 символов): {text[:100]}...")
            logger.info(f"   🖼️  Есть фото: {'ДА' if img_url else 'НЕТ'}")
            logger.info(f"   🆔 ID: {post_id[:16]}...")
            
            return {
                'id': post_id,
                'text': text,
                'date': date_str,
                'image_url': img_url,
                'channel': channel_name
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга поста: {e}")
            return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return None

def download_image(url):
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
    except Exception as e:
        logger.error(f"❌ Ошибка скачивания: {e}")
    return None

# ==================== ОСНОВНОЙ БОТ ====================

class RSSBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.target_chat = TARGET_CHANNEL_ID
        self.last_posts = load_last_posts()
        self.running = True
        
    async def stop(self):
        self.running = False
        logger.info("🛑 Бот останавливается...")
        
    async def check_channels(self):
        logger.info("="*60)
        logger.info("🔍 НАЧАЛО ПРОВЕРКИ КАНАЛОВ")
        logger.info("="*60)
        
        new_posts = 0
        
        for channel in SOURCE_CHANNEL_LIST:
            logger.info(f"\n📢 Обработка канала: {channel}")
            logger.info(f"   Последние обработанные ID: {self.last_posts.get(channel, [])[-3:]}")
            
            try:
                post = get_latest_post(channel)
                
                if not post:
                    logger.warning(f"⚠️ Не удалось получить пост из {channel}")
                    continue
                
                if post['id'] in self.last_posts.get(channel, []):
                    logger.info(f"⏭️ Пост УЖЕ обработан (ID: {post['id'][:16]}...)")
                    continue
                
                logger.info(f"✨ НОВЫЙ пост в {channel} (ID: {post['id'][:16]}...)")
                new_posts += 1
                
                await self.process_post(post)
                
                if channel not in self.last_posts:
                    self.last_posts[channel] = []
                self.last_posts[channel].append(post['id'])
                
                if len(self.last_posts[channel]) > 50:
                    self.last_posts[channel] = self.last_posts[channel][-50:]
                
                save_last_posts(self.last_posts)
                logger.info(f"💾 ID сохранен в историю")
                
            except Exception as e:
                logger.error(f"❌ Ошибка {channel}: {e}")
        
        logger.info("="*60)
        if new_posts == 0:
            logger.info("ℹ️ НОВЫХ ПОСТОВ НЕТ")
        else:
            logger.info(f"✅ ОБРАБОТАНО {new_posts} НОВЫХ ПОСТОВ")
        logger.info("="*60)
    
    async def process_post(self, post):
        try:
            text = post.get('text', '')
            title = extract_title(text)
            
            logger.info(f"🔄 ОБРАБОТКА ПОСТА:")
            logger.info(f"   📝 Оригинальный текст: {text[:150]}..." if len(text) > 150 else f"   📝 Оригинальный текст: {text}")
            logger.info(f"   🏷️  Заголовок для фото: {title}")
            
            if post.get('image_url'):
                logger.info("📸 Есть фото, обрабатываем...")
                img_data = download_image(post['image_url'])
                if img_data:
                    processed = process_photo_bytes(img_data, title)
                    
                    await self.bot.send_photo(
                        chat_id=self.target_chat,
                        photo=BytesIO(processed.getvalue()),
                        caption=text[:1024] if text else "",
                        parse_mode="HTML"
                    )
                    logger.info("✅ ФОТО УСПЕШНО ОТПРАВЛЕНО В КАНАЛ!")
                    return
            
            if text:
                logger.info("📝 Только текст, отправляем как есть")
                await self.bot.send_message(
                    chat_id=self.target_chat,
                    text=text,
                    parse_mode="HTML"
                )
                logger.info("✅ ТЕКСТ УСПЕШНО ОТПРАВЛЕН В КАНАЛ!")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки: {e}")

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = sum(len(v) for v in bot.last_posts.values())
    await update.message.reply_text(
        f"🤖 <b>Бот для репоста</b>\n\n"
        f"📢 Каналы: {', '.join(SOURCE_CHANNEL_LIST)}\n"
        f"📢 Целевой канал: <code>{TARGET_CHANNEL_ID}</code>\n"
        f"⏱ Интервал: {CHECK_INTERVAL}с\n"
        f"📊 Обработано: {total}\n\n"
        f"✅ Бот работает!",
        parse_mode="HTML"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = sum(len(v) for v in bot.last_posts.values())
    msg = f"📊 <b>Статистика</b>\n\n"
    msg += f"📨 Всего обработано: {total}\n"
    msg += f"📢 Каналов: {len(SOURCE_CHANNEL_LIST)}\n"
    msg += f"⏱ Интервал: {CHECK_INTERVAL}с\n\n"
    msg += "<b>По каналам:</b>\n"
    for ch in SOURCE_CHANNEL_LIST:
        count = len(bot.last_posts.get(ch, []))
        msg += f"  • {ch}: {count} постов\n"
    
    await update.message.reply_text(msg, parse_mode="HTML")

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Проверка...")
    await bot.check_channels()
    await update.message.reply_text("✅ Готово!")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot.last_posts = {}
    save_last_posts({})
    await update.message.reply_text("✅ История сброшена!")

# ==================== ЗАПУСК ====================

async def main():
    global bot, app
    
    logger.info("⏳ Ожидание завершения старых экземпляров (10 сек)...")
    await asyncio.sleep(10)
    
    bot = RSSBot()
    
    logger.info("="*60)
    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")
    logger.info(f"📊 Каналы: {SOURCE_CHANNEL_LIST}")
    logger.info(f"⏱ Интервал: {CHECK_INTERVAL}с")
    logger.info("="*60)
    
    download_fonts()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления webhook: {e}")
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(CommandHandler("reset", reset))
    
    await app.initialize()
    await app.start()
    
    await app.updater.start_polling(
        allowed_updates=["message"],
        drop_pending_updates=True,
        poll_interval=2.0,
        timeout=60,
        read_timeout=60,
        write_timeout=60,
        connect_timeout=60
    )
    
    logger.info("🟢 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    
    await asyncio.sleep(5)
    
    while bot.running:
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
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)
