from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from services import DeepSeekService
import os
from datetime import datetime
import traceback
import re

logger = logging.getLogger(__name__)

# Инициализация DeepSeek
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
        logger.error(f"❌ Ошибка инициализации DeepSeek: {e}")
        deepseek = None

# Константы
NEWS_CALLBACK = "news"
EVENTS_CALLBACK = "events"
WEATHER_CURRENCY_CALLBACK = "weather_currency"

# Хранилище
user_states = {}

def safe_markdown(text: str) -> str:
    """Очищает текст от проблемных Markdown-символов"""
    # Экранируем специальные символы
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    # Проверяем и исправляем незакрытые жирные/курсивные теги
    # Считаем количество открывающих и закрывающих **
    bold_open = text.count('**')
    if bold_open % 2 != 0:
        # Если нечетное количество - закрываем последний
        text = text + '**'
    
    # Экранируем специальные символы, но не экранируем маркдаун
    # Просто заменяем проблемные комбинации
    text = text.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
    
    return text

def clean_text_for_telegram(text: str) -> str:
    """Очищает текст для отправки в Telegram без ошибок Markdown"""
    # Удаляем лишние переносы
    text = text.strip()
    
    # Проверяем парность маркдаун-тегов
    # Bold: **текст**
    import re
    bold_pattern = r'\*\*[^*]+\*\*'
    bold_matches = re.findall(bold_pattern, text)
    
    # Если есть незакрытые **, заменяем их на обычный текст
    text = re.sub(r'\*\*([^*]+)$', r'\\*\\*\\1', text)  # незакрытый в конце
    text = re.sub(r'^\*\*([^*]+)', r'\\*\\*\\1', text)   # незакрытый в начале
    
    # Для надежности - просто удаляем все одиночные *
    text = re.sub(r'(?<!\*)\*(?!\*)', '', text)
    
    return text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    try:
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"👤 Пользователь {user_id} запустил бота")
        
        if user_id not in user_states:
            user_states[user_id] = {
                'active': True,
                'requests_count': 0,
                'last_active': datetime.now(),
                'created_at': datetime.now()
            }
        
        welcome_text = (
            "👋 Привет! Я твой помощник по Минску.\n\n"
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
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        logger.info(f"✅ Меню отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в start_command: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"🔘 Пользователь {user_id} нажал: {callback_data}")
        
        await query.answer()
        
        if deepseek is None:
            await query.edit_message_text(
                "❌ Сервис временно недоступен. Попробуйте позже."
            )
            return
        
        # Статистика
        if user_id in user_states:
            user_states[user_id]['requests_count'] += 1
            user_states[user_id]['last_active'] = datetime.now()
        
        # Сообщение о загрузке
        loading_msg = await query.edit_message_text(
            "🔍 Ищу информацию...\n⏳ Это может занять 10-15 секунд."
        )
        
        # Генерация ответа
        if callback_data == NEWS_CALLBACK:
            result = await deepseek.generate_news_digest()
            prefix = f"📰 НОВОСТИ\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        elif callback_data == EVENTS_CALLBACK:
            result = await deepseek.generate_events_digest()
            prefix = f"🎭 АФИША\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        elif callback_data == WEATHER_CURRENCY_CALLBACK:
            result = await deepseek.generate_weather_currency_digest()
            prefix = f"🌤️ ПОГОДА И КУРСЫ\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
        else:
            result = "❌ Неизвестная команда"
            prefix = ""
        
        full_response = prefix + result + f"\n\n---\n🕐 {datetime.now().strftime('%H:%M')}"
        
        # Очищаем текст от проблемных символов
        clean_response = clean_text_for_telegram(full_response)
        
        # Отправляем с parse_mode=None (обычный текст)
        await loading_msg.edit_text(clean_response)
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в button_handler: {e}")
        logger.error(traceback.format_exc())
        try:
            # Отправляем без форматирования
            error_text = f"❌ Ошибка: {str(e)[:200]}\n\nПопробуйте позже."
            await query.edit_message_text(error_text)
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста"""
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
        full_response = result + f"\n\n---\n🕐 {datetime.now().strftime('%H:%M')}"
        
        # Очищаем текст
        clean_response = clean_text_for_telegram(full_response)
        
        if len(clean_response) > 4000:
            for i in range(0, len(clean_response), 4000):
                await update.message.reply_text(clean_response[i:i+4000])
            await loading.delete()
        else:
            await loading.edit_text(clean_response)
            
    except Exception as e:
        logger.error(f"❌ Ошибка в handle_text: {e}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_states:
        user_states[user_id]['active'] = False
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
    user_id = update.effective_user.id
    if user_id in user_states:
        stats = user_states[user_id]
        text = (
            f"📊 Статистика:\n\n"
            f"Запросов: {stats.get('requests_count', 0)}\n"
            f"Активен: {'✅ Да' if stats.get('active', True) else '❌ Нет'}"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Нет статистики. Нажмите /start")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = str(context.error)
    if "Conflict" not in error:
        logger.error(f"❌ Ошибка: {error}")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Неизвестная команда. Используйте /help")
