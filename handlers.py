from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from services import DeepSeekService
import os
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

# Инициализируем сервис DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

if not DEEPSEEK_API_KEY:
    logger.error("❌ DEEPSEEK_API_KEY не найден")
    deepseek = None
else:
    deepseek = DeepSeekService(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )
    logger.info("✅ DeepSeek сервис инициализирован")

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
            "Я - твой персональный помощник по Минску с доступом к интернету.\n\n"
            "📌 **Я могу:**\n"
            "📰 Найти свежие новости за сегодня\n"
            "🎭 Подобрать мероприятия на сегодня\n"
            "🌤️ Рассказать о погоде и курсах валют\n"
            "❓ Ответить на любой вопрос\n\n"
            "Выбери, что тебя интересует:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📰 Новости за сегодня", callback_data=NEWS_CALLBACK)],
            [InlineKeyboardButton("🎭 Афиша на сегодня", callback_data=EVENTS_CALLBACK)],
            [InlineKeyboardButton("🌤️ Погода и курсы валют", callback_data=WEATHER_CURRENCY_CALLBACK)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
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
        
        logger.info(f"🔘 Пользователь {user_id} нажал кнопку: {callback_data}")
        
        # Отвечаем на callback
        await query.answer()
        
        # Проверяем DeepSeek
        if deepseek is None:
            await query.edit_message_text(
                "❌ Сервис DeepSeek не инициализирован.\n"
                "Пожалуйста, проверьте настройки DEEPSEEK_API_KEY на Render."
            )
            return
        
        # Обновляем статистику
        user_states[user_id]['requests_count'] += 1
        user_states[user_id]['last_active'] = datetime.now()
        
        # Показываем загрузку
        loading_message = await query.edit_message_text(
            "🔍 Ищу актуальную информацию в интернете...\n"
            "⏳ Это может занять 10-15 секунд.\n\n"
            "🔄 Пожалуйста, подождите..."
        )
        
        # Генерируем ответ
        if callback_data == NEWS_CALLBACK:
            logger.info(f"📰 Запрос новостей от {user_id}")
            result = await deepseek.generate_news_digest()
            prefix = "📰 **ДАЙДЖЕСТ НОВОСТЕЙ**\n"
            prefix += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            
        elif callback_data == EVENTS_CALLBACK:
            logger.info(f"🎭 Запрос афиши от {user_id}")
            result = await deepseek.generate_events_digest()
            prefix = "🎭 **АФИША МЕРОПРИЯТИЙ**\n"
            prefix += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            
        elif callback_data == WEATHER_CURRENCY_CALLBACK:
            logger.info(f"🌤️ Запрос погоды и курсов от {user_id}")
            result = await deepseek.generate_weather_currency_digest()
            prefix = "🌤️ **ПОГОДА И КУРСЫ ВАЛЮТ**\n"
            prefix += f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            
        else:
            result = "❌ Неизвестная команда"
            prefix = ""
        
        # Формируем полный ответ
        footer = f"\n\n---\n🕐 Обновлено: {datetime.now().strftime('%H:%M')}"
        full_response = prefix + result + footer
        
        logger.info(f"✅ Ответ сгенерирован, длина: {len(full_response)} символов")
        
        # Отправляем ответ
        await loading_message.edit_text(full_response, parse_mode='Markdown')
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в button_handler: {e}")
        logger.error(traceback.format_exc())
        try:
            await query.edit_message_text(
                f"❌ Произошла ошибка: {str(e)}\n\n"
                "Пожалуйста, попробуйте позже."
            )
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    try:
        user_id = update.effective_user.id
        user_message = update.message.text
        logger.info(f"💬 Пользователь {user_id} написал: {user_message[:50]}...")
        
        if user_message.startswith('/'):
            return
        
        if deepseek is None:
            await update.message.reply_text(
                "❌ Сервис DeepSeek не инициализирован.\n"
                "Пожалуйста, проверьте настройки."
            )
            return
        
        # Показываем загрузку
        loading_message = await update.message.reply_text(
            "🔍 Ищу информацию...\n"
            "⏳ Это может занять несколько секунд."
        )
        
        # Обрабатываем запрос
        result = await deepseek.custom_query(user_message)
        
        footer = f"\n\n---\n🕐 Ответ актуален на {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        full_response = result + footer
        
        # Разбиваем длинные сообщения
        if len(full_response) > 4000:
            for i in range(0, len(full_response), 4000):
                await update.message.reply_text(full_response[i:i+4000], parse_mode='Markdown')
            await loading_message.delete()
        else:
            await loading_message.edit_text(full_response, parse_mode='Markdown')
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке текстового запроса: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}\n\n"
            "Попробуйте переформулировать запрос."
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"🛑 Пользователь {user_id} остановил бота")
    
    if user_id in user_states:
        user_states[user_id]['active'] = False
    
    await update.message.reply_text(
        "🛑 Бот отключен.\n"
        "Чтобы снова начать пользоваться, нажмите /start"
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"🔄 Пользователь {user_id} перезапустил бота")
    
    if user_id in user_states:
        user_states[user_id]['active'] = True
    
    await start_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 **Помощь по боту:**\n\n"
        "📌 **Команды:**\n"
        "/start - Запустить бота\n"
        "/restart - Перезапустить бота\n"
        "/stop - Отключить бота\n"
        "/help - Показать справку\n"
        "/stats - Статистика использования\n\n"
        "📌 **Как пользоваться:**\n"
        "• Нажми на кнопку с нужной категорией\n"
        "• Или просто напиши свой вопрос\n\n"
        "📌 **Примеры вопросов:**\n"
        "• \"Куда сходить с детьми сегодня?\"\n"
        "• \"Какие новые фильмы в Минске?\"\n"
        "• \"Что происходит в Беларуси?\""
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_states:
        stats = user_states[user_id]
        days_active = (datetime.now() - stats.get('created_at', datetime.now())).days
        stats_text = (
            "📊 **Ваша статистика:**\n\n"
            f"• Запросов: {stats.get('requests_count', 0)}\n"
            f"• Активен: {'✅ Да' if stats.get('active', True) else '❌ Нет'}\n"
            f"• Дней: {days_active}\n"
            f"• Последний запрос: {stats.get('last_active', datetime.now()).strftime('%H:%M %d.%m.%Y')}"
        )
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    else:
        await update.message.reply_text("Статистика не найдена. Нажмите /start")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error_msg = str(context.error)
    logger.error(f"❌ Ошибка: {error_msg}")
    
    if "Conflict" in error_msg:
        return
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка.\n"
                "Попробуйте позже или нажмите /start"
            )
    except:
        pass

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Неизвестная команда.\n"
        "Используйте /help для просмотра команд"
    )
