from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
from services import DeepSeekService
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Инициализируем сервис DeepSeek
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

if not DEEPSEEK_API_KEY:
    logger.error("❌ DEEPSEEK_API_KEY не найден в переменных окружения")
    raise ValueError("DEEPSEEK_API_KEY is required")

deepseek = DeepSeekService(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# Константы для callback_data
NEWS_CALLBACK = "news"
EVENTS_CALLBACK = "events"
WEATHER_CURRENCY_CALLBACK = "weather_currency"

# Хранилище состояний пользователей
user_states = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    if user_id not in user_states:
        user_states[user_id] = {
            'active': True, 
            'requests_count': 0, 
            'last_active': datetime.now(),
            'created_at': datetime.now()
        }
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я - твой персональный помощник на основе ИИ с доступом к интернету. "
        "Я могу найти для тебя актуальную информацию о Минске и Беларуси:\n\n"
        "📰 Свежие новости за сегодня\n"
        "🎭 Афишу мероприятий на сегодня\n"
        "🌤️ Прогноз погоды и курсы валют\n"
        "❓ Или задай свой вопрос\n\n"
        "Выбери категорию или просто напиши свой вопрос:"
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

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, активен ли пользователь
    if user_id not in user_states or not user_states[user_id].get('active', True):
        await query.edit_message_text("❌ Бот отключен. Для активации нажмите /start")
        return
    
    # Обновляем статистику
    user_states[user_id]['requests_count'] += 1
    user_states[user_id]['last_active'] = datetime.now()
    
    # Отправляем сообщение о начале обработки
    loading_message = await query.edit_message_text(
        "🔍 Ищу актуальную информацию в интернете...\n"
        "Это может занять 5-10 секунд."
    )
    
    try:
        if query.data == NEWS_CALLBACK:
            result = await deepseek.generate_news_digest()
            prefix = "📰 **Дайджест новостей на сегодня**\n\n"
        elif query.data == EVENTS_CALLBACK:
            result = await deepseek.generate_events_digest()
            prefix = "🎭 **Афиша мероприятий на сегодня**\n\n"
        elif query.data == WEATHER_CURRENCY_CALLBACK:
            result = await deepseek.generate_weather_currency_digest()
            prefix = "🌤️ **Погода и курсы валют на сегодня**\n\n"
        else:
            result = "❌ Неизвестная команда"
            prefix = ""
        
        # Добавляем информацию о том, что данные актуальны
        footer = f"\n\n---\n🕐 Данные актуальны на {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        full_response = prefix + result + footer
        
        await loading_message.edit_text(full_response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Ошибка в button_handler: {e}")
        await loading_message.edit_text(
            f"❌ Произошла ошибка при обработке запроса: {str(e)}\n\n"
            "Пожалуйста, попробуйте позже или напишите свой вопрос текстом."
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (произвольные вопросы)"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Проверяем, активен ли пользователь
    if user_id not in user_states or not user_states[user_id].get('active', True):
        await update.message.reply_text("❌ Бот отключен. Для активации нажмите /start")
        return
    
    # Игнорируем команды
    if user_message.startswith('/'):
        return
    
    # Обновляем статистику
    user_states[user_id]['requests_count'] += 1
    user_states[user_id]['last_active'] = datetime.now()
    
    # Отправляем сообщение о начале поиска
    loading_message = await update.message.reply_text(
        "🔍 Ищу информацию по вашему запросу...\n"
        "Это может занять несколько секунд."
    )
    
    try:
        # Обрабатываем запрос через DeepSeek с поиском
        result = await deepseek.custom_query(user_message)
        
        # Добавляем информацию об актуальности
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
        logger.error(f"Ошибка при обработке текстового запроса: {e}")
        await loading_message.edit_text(
            f"❌ Произошла ошибка при поиске информации: {str(e)}\n\n"
            "Попробуйте переформулировать запрос или нажмите /start для перезапуска."
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop"""
    user_id = update.effective_user.id
    
    if user_id in user_states:
        user_states[user_id]['active'] = False
    
    await update.message.reply_text(
        "🛑 Бот отключен. Чтобы снова начать пользоваться, нажмите /start"
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапуск бота"""
    user_id = update.effective_user.id
    
    if user_id in user_states:
        user_states[user_id]['active'] = True
    
    await start_command(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 **Помощь по боту:**\n\n"
        "📌 **Команды:**\n"
        "/start - Запустить бота и показать главное меню\n"
        "/help - Показать эту справку\n"
        "/stop - Отключить бота\n"
        "/restart - Перезапустить бота\n"
        "/stats - Показать статистику использования\n\n"
        "📌 **Как пользоваться:**\n"
        "1. Используй кнопки для быстрого доступа к информации\n"
        "2. Или просто напиши свой вопрос текстом\n\n"
        "📌 **Примеры запросов:**\n"
        "• \"Где сегодня можно сходить с детьми в Минске?\"\n"
        "• \"Какие фильмы идут в кинотеатрах Минска?\"\n"
        "• \"Какая ситуация с ценами на продукты?\"\n"
        "• \"Что нового в белорусской экономике?\"\n\n"
        "📌 **Важно:**\n"
        "• Все данные ищутся в реальном времени\n"
        "• Ответы основаны на актуальной информации из интернета\n"
        "• Бот использует ИИ для анализа и структурирования данных"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику использования"""
    user_id = update.effective_user.id
    
    if user_id in user_states:
        stats = user_states[user_id]
        days_active = (datetime.now() - stats.get('created_at', datetime.now())).days
        stats_text = (
            "📊 **Ваша статистика:**\n\n"
            f"• Запросов выполнено: {stats.get('requests_count', 0)}\n"
            f"• Последний запрос: {stats.get('last_active', datetime.now()).strftime('%H:%M %d.%m.%Y')}\n"
            f"• Статус: {'✅ Активен' if stats.get('active', True) else '❌ Отключен'}\n"
            f"• Время работы: {days_active} дней"
        )
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    else:
        await update.message.reply_text("Статистика не найдена. Нажмите /start для начала работы.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или нажмите /start для перезапуска."
            )
    except:
        pass

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик неизвестных команд"""
    await update.message.reply_text(
        "❓ Неизвестная команда.\n"
        "Используйте /help для просмотра доступных команд\n"
        "Или просто напишите свой вопрос."
    )
