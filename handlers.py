from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

# Константы для callback_data
NEWS_CALLBACK = "news"
EVENTS_CALLBACK = "events"
WEATHER_CURRENCY_CALLBACK = "weather_currency"

# Хранилище состояний пользователей
user_states = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user = update.effective_user
        user_id = user.id
        logger.info(f"👤 Пользователь {user_id} ({user.first_name}) запустил бота")
        
        if user_id not in user_states:
            user_states[user_id] = {
                'active': True, 
                'requests_count': 0, 
                'last_active': datetime.now(),
                'created_at': datetime.now()
            }
        
        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            "Я - твой помощник. Нажми на кнопку ниже:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📰 Новости за сегодня", callback_data=NEWS_CALLBACK),
            ],
            [
                InlineKeyboardButton("🎭 Афиша на сегодня", callback_data=EVENTS_CALLBACK),
            ],
            [
                InlineKeyboardButton("🌤️ Погода и курсы валют", callback_data=WEATHER_CURRENCY_CALLBACK),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        logger.info(f"✅ Отправлено меню пользователю {user_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка в start_command: {e}")
        logger.error(traceback.format_exc())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"🔘🔘🔘 Пользователь {user_id} НАЖАЛ КНОПКУ: {callback_data} 🔘🔘🔘")
        
        # Отвечаем на callback
        await query.answer()
        
        # Простой ответ
        responses = {
            NEWS_CALLBACK: "📰 Вы выбрали **Новости**!\n\nЭто тестовый ответ. Бот работает!",
            EVENTS_CALLBACK: "🎭 Вы выбрали **Афишу**!\n\nЭто тестовый ответ. Бот работает!",
            WEATHER_CURRENCY_CALLBACK: "🌤️ Вы выбрали **Погоду и курсы валют**!\n\nЭто тестовый ответ. Бот работает!"
        }
        
        response = responses.get(callback_data, "❌ Неизвестная команда")
        
        # Отправляем ответ
        await query.edit_message_text(response, parse_mode='Markdown')
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в button_handler: {e}")
        logger.error(traceback.format_exc())
        try:
            await query.edit_message_text(f"❌ Ошибка: {str(e)}")
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        user_id = update.effective_user.id
        user_message = update.message.text
        logger.info(f"💬 Пользователь {user_id} написал: {user_message}")
        
        if user_message.startswith('/'):
            return
        
        await update.message.reply_text(
            f"Вы написали: {user_message}\n\n"
            "Используйте кнопки для получения информации."
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке текстового запроса: {e}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"🛑 Пользователь {user_id} остановил бота")
    await update.message.reply_text("🛑 Бот отключен. Для активации нажмите /start")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = "🤖 **Помощь:**\n\n/start - Запустить бота\n/stop - Отключить бота\n/help - Помощь"
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Бот работает нормально!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error_msg = str(context.error)
    logger.error(f"❌ Глобальная ошибка: {error_msg}")
    if "Conflict" not in error_msg:
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text("❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❓ Неизвестная команда. Используйте /help")
