from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from services import DeepSeekService
import os
from datetime import datetime
import traceback
import re

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

if not DEEPSEEK_API_KEY:
    logger.error("❌ DEEPSEEK_API_KEY не найден")
    deepseek = None
else:
    try:
        deepseek = DeepSeekService(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL
        )
        logger.info("✅ DeepSeek сервис инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        deepseek = None

NEWS_CALLBACK = "news"
EVENTS_CALLBACK = "events"
WEATHER_CURRENCY_CALLBACK = "weather_currency"

user_states = {}

def clean_text(text: str) -> str:
    """Очистка текста"""
    if not text:
        return text
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()

def split_news(text: str) -> list:
    """Разбивка новостей по 5 штук"""
    if not text:
        return [text]
    
    # Ищем новости по паттерну 📌
    items = re.findall(r'📌.*?(?=📌|$)', text, re.DOTALL)
    
    if len(items) <= 5:
        return [text]
    
    result = []
    for i in range(0, len(items), 5):
        chunk = ''.join(items[i:i+5])
        if i == 0:
            result.append(chunk)
        else:
            result.append(f"📰 Продолжение ({i//5 + 1})\n\n{chunk}")
    
    return result

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"👤 Пользователь {user_id} запустил бота")
        
        welcome_text = (
            "👋 Привет!\n\n"
            "📌 Что я умею:\n"
            "📰 Новости за сегодня\n"
            "🎭 Афиша на сегодня\n"
            "🌤️ Погода и курсы валют\n"
            "❓ Ответить на любой вопрос\n\n"
            "Выбери, что тебя интересует:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📰 Новости", callback_data=NEWS_CALLBACK)],
            [InlineKeyboardButton("🎭 Афиша", callback_data=EVENTS_CALLBACK)],
            [InlineKeyboardButton("🌤️ Погода и курсы", callback_data=WEATHER_CURRENCY_CALLBACK)]
        ]
        
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
        logger.info(f"✅ Меню отправлено")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"🔘 Пользователь {user_id} нажал: {callback_data}")
        
        await query.answer()
        
        if deepseek is None:
            await query.edit_message_text("❌ Сервис временно недоступен.")
            return
        
        loading = await query.edit_message_text("🔍 Ищу информацию... ⏳ 10-15 секунд")
        
        if callback_data == NEWS_CALLBACK:
            logger.info("📰 Новости...")
            result = await deepseek.generate_news_digest()
            
            # Разбиваем по 5 новостей
            parts = split_news(result)
            
            await loading.edit_text(clean_text(parts[0]))
            for part in parts[1:]:
                await query.message.reply_text(clean_text(part))
            
            logger.info(f"✅ Отправлено {len(parts)} частей")
            
        elif callback_data == EVENTS_CALLBACK:
            logger.info("🎭 Афиша...")
            result = await deepseek.generate_events_digest()
            await loading.edit_text(clean_text(result))
            
        elif callback_data == WEATHER_CURRENCY_CALLBACK:
            logger.info("🌤️ Погода...")
            result = await deepseek.generate_weather_currency_digest()
            await loading.edit_text(clean_text(result))
            
        else:
            await loading.edit_text("❌ Неизвестная команда")
        
        logger.info(f"✅ Ответ отправлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        logger.error(traceback.format_exc())
        try:
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:200]}")
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        if text.startswith('/'):
            return
        
        logger.info(f"💬 Пользователь {user_id}: {text[:50]}...")
        
        if deepseek is None:
            await update.message.reply_text("❌ Сервис временно недоступен.")
            return
        
        loading = await update.message.reply_text("🔍 Ищу ответ...")
        
        result = await deepseek.custom_query(text)
        clean_result = clean_text(result)
        
        if len(clean_result) > 4000:
            for i in range(0, len(clean_result), 4000):
                await update.message.reply_text(clean_result[i:i+4000])
            await loading.delete()
        else:
            await loading.edit_text(clean_result)
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Бот отключен. Нажмите /start для активации.")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 Помощь:\n\n"
        "/start - Запустить бота\n"
        "/stop - Отключить бота\n"
        "/help - Эта справка\n"
        "/stats - Статистика\n\n"
        "Используй кнопки или задай вопрос текстом."
    )
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Бот работает!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = str(context.error)
    if "Conflict" not in error:
        logger.error(f"❌ Ошибка: {error}")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Неизвестная команда. Используйте /help")
