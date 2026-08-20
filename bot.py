# -*- coding: utf-8 -*-

import os
import re
import logging
import sys
from io import BytesIO
from datetime import datetime, timedelta
import hashlib
import json
import requests
import feedparser
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

# ==================== НАСТРОЙКИ ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "")  # Имена каналов через запятую
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
MAX_POST_AGE_MINUTES = int(os.getenv("MAX_POST_AGE_MINUTES", "5"))

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

# ==================== ПАРСИНГ RSS ====================

def get_rss_items_for_channel(channel_name):
    """Получение RSS из готового сервиса"""
    try:
        rss_url = f"https://telegram-rss-parser-web.vercel.app/{channel_name}"
        logger.info(f"📡 Запрос к RSS: {rss_url}")
        
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            logger.warning(f"⚠️ Нет постов в {channel_name}")
            return []
        
        items = []
        for entry in feed.entries[:10]:
            pub_date = None
            if hasattr(entry, 'published_parsed'):
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
                'channel': channel_name
            })
        
        logger.info(f"✅ Получено {len(items)} постов из {channel_name}")
        
        logger.info(f"📋 Последние посты из {channel_name}:")
        for i, item in enumerate(items[:5]):
            title = item['title'][:50] if item['title'] else item['description'][:50]
            date = item['pubDate'].strftime('%H:%M') if item['pubDate'] else 'нет даты'
            logger.info(f"  [{i+1}] {date}: {title}...")
        
        return items
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения RSS для {channel_name}: {e}")
        return []

def download_image(url):
    try:
        if not url:
            return None
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
        
    async def check_channels(self):
        logger.info("="*60)
        logger.info("🔍 ПРОВЕРКА КАНАЛОВ (RSS)")
        logger.info("="*60)
        
        new_posts = 0
        
        for channel in SOURCE_CHANNEL_LIST:
            logger.info(f"\n📢 Канал: {channel}")
            
            try:
                items = get_rss_items_for_channel(channel)
                
                if not items:
                    logger.info(f"⏭️ Нет постов в {channel}")
                    continue
                
                latest_item = items[0]
                
                if latest_item.get('pubDate'):
                    age_minutes = (datetime.now() - latest_item['pubDate']).total_seconds() / 60
                    if age_minutes > MAX_POST_AGE_MINUTES:
                        logger.info(f"⏭️ Пост старый ({age_minutes:.1f} мин) - пропускаем")
                        continue
                
                if latest_item['id'] in self.last_posts.get(channel, []):
                    logger.info(f"⏭️ Пост уже обработан")
                    continue
                
                logger.info(f"✨ НОВЫЙ ПОСТ в {channel}!")
                new_posts += 1
                
                await self.process_post(latest_item, channel)
                
                if channel not in self.last_posts:
                    self.last_posts[channel] = []
                self.last_posts[channel].append(latest_item['id'])
                
                if len(self.last_posts[channel]) > 50:
                    self.last_posts[channel] = self.last_posts[channel][-50:]
                
                save_last_posts(self.last_posts)
                logger.info(f"💾 Сохранено в историю")
                
            except Exception as e:
                logger.error(f"❌ Ошибка {channel}: {e}")
        
        logger.info("="*60)
        if new_posts == 0:
            logger.info("ℹ️ НОВЫХ ПОСТОВ НЕТ")
        else:
            logger.info(f"✅ ОБРАБОТАНО {new_posts} ПОСТОВ")
        logger.info("="*60)
    
    async def process_post(self, item, channel):
        try:
            full_text = item.get('description') or item.get('title') or ""
            photo_title = extract_title(full_text)
            
            logger.info(f"🔄 ОБРАБОТКА:")
            logger.info(f"   📝 Текст: {full_text[:150]}..." if len(full_text) > 150 else f"   📝 Текст: {full_text}")
            logger.info(f"   🏷️ Заголовок: {photo_title}")
            
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
                    logger.info("✅ ФОТО ОТПРАВЛЕНО!")
                    return
            
            if full_text:
                logger.info("📝 Только текст")
                await self.bot.send_message(
                    chat_id=self.target_chat,
                    text=full_text,
                    parse_mode="HTML"
                )
                logger.info("✅ ТЕКСТ ОТПРАВЛЕН!")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки: {e}")

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = sum(len(v) for v in bot.last_posts.values())
    await update.message.reply_text(
        f"🤖 <b>Бот для репоста (RSS)</b>\n\n"
        f"📢 Каналы: {', '.join(SOURCE_CHANNEL_LIST)}\n"
        f"📢 Целевой канал: <code>{TARGET_CHANNEL_ID}</code>\n"
        f"⏱ Интервал: {CHECK_INTERVAL}с\n"
        f"⏳ Макс. возраст: {MAX_POST_AGE_MINUTES} мин\n"
        f"📊 Обработано: {total}\n\n"
        f"✅ Бот работает!",
        parse_mode="HTML"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = sum(len(v) for v in bot.last_posts.values())
    msg = f"📊 <b>Статистика</b>\n\n"
    msg += f"📨 Всего обработано: {total}\n"
    msg += f"⏱ Интервал: {CHECK_INTERVAL}с\n"
    msg += f"⏳ Макс. возраст: {MAX_POST_AGE_MINUTES} мин\n\n"
    msg += "<b>По каналам:</b>\n"
    for ch, ids in bot.last_posts.items():
        msg += f"  • {ch}: {len(ids)} постов\n"
    
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
    
    logger.info("⏳ Ожидание (10 сек)...")
    await asyncio.sleep(10)
    
    bot = RSSBot()
    
    logger.info("="*60)
    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ (RSS)")
    logger.info(f"📢 Каналы: {SOURCE_CHANNEL_LIST}")
    logger.info(f"⏱ Интервал: {CHECK_INTERVAL}с")
    logger.info(f"⏳ Макс. возраст: {MAX_POST_AGE_MINUTES} мин")
    logger.info("="*60)
    
    download_fonts()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка: {e}")
    
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
    
    logger.info("🟢 БОТ ЗАПУЩЕН!")
    
    await asyncio.sleep(5)
    
    while bot.running:
        try:
            await bot.check_channels()
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        sys.exit(0)
