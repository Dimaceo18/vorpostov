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
    logger.error("❌ DEEPSEEK_API_KEY не найден в переменных окружения")
    deepseek = None
    logger.warning("⚠️ DeepSeek сервис не инициализирован")
else:
    deepseek = DeepSeekService(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )
    logger.info("✅ DeepSeek сервис успешно инициализирован")

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
    logger.info(f"✅ Отправлено меню пользователю {user_id}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    try:
        query = update.callback_query
        user_id = query.from_user.id
        callback_data = query.data
        
        logger.info(f"🔘 Пользователь {user_id} нажал кнопку: {callback_data}")
        
        # Отвечаем на callback
        await query.answer()
        
        # Проверяем, активен ли пользователь
        if user_id not in user_states or not user_states[user_id].get('active', True):
            await query.edit_message_text("❌ Бот отключен. Для активации нажмите /start")
            return
        
        # Проверяем, инициализирован ли DeepSeek
        if deepseek is None:
            await query.edit_message_text(
                "❌ Сервис DeepSeek не инициализирован. "
                "Пожалуйста, проверьте настройки DEEPSEEK_API_KEY на Render."
            )
            return
        
        # Обновляем статистику
        user_states[user_id]['requests_count'] += 1
        user_states[user_id]['last_active'] = datetime.now()
        
        # Отправляем сообщение о начале обработки
        loading_message = await query.edit_message_text(
            "🔍 Ищу актуальную информацию в интернете...\n"
            "⏳ Это может занять 5-15 секунд.\n\n"
            "🔄 Пожалуйста, подождите..."
        )
        logger.info(f"⏳ Начат поиск для пользователя {user_id} по запросу: {callback_data}")
        
        # Обрабатываем запрос
        if callback_data == NEWS_CALLBACK:
            logger.info(f"📰 Запрос новостей от {user_id}")
            result = await deepseek.generate_news_digest()
            prefix = "📰 **Дайджест новостей на сегодня**\n\n"
        elif callback_data == EVENTS_CALLBACK:
            logger.info(f"🎭 Запрос афиши от {user_id}")
            result = await deepseek.generate_events_digest()
            prefix = "🎭 **Афиша мероприятий на сегодня**\n\n"
        elif callback_data == WEATHER_CURRENCY_CALLBACK:
            logger.info(f"🌤️ Запрос погоды и курсов от {user_id}")
            result = await deepseek.generate_weather_currency_digest()
            prefix = "🌤️ **Погода и курсы валют на сегодня**\n\n"
        else:
            result = "❌ Неизвестная команда"
            prefix = ""
        
        # Добавляем информацию о том, что данные актуальны
        footer = f"\n\n---\n🕐 Данные актуальны на {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        full_response = prefix + result + footer
        
        logger.info(f"✅ Ответ сгенерирован для пользователя {user_id}, длина: {len(full_response)} символов")
        
        # Отправляем ответ
        await loading_message.edit_text(full_response, parse_mode='Markdown')
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в button_handler: {e}")
        logger.error(traceback.format_exc())
        try:
            await query.edit_message_text(
                f"❌ Произошла ошибка при обработке запроса: {str(e)}\n\n"
                "Пожалуйста, попробуйте позже или напишите свой вопрос текстом."
            )
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (произвольные вопросы)"""
    try:
        user_id = update.effective_user.id
        user_message = update.message.text
        logger.info(f"💬 Пользователь {user_id} написал: {user_message[:50]}...")
        
        # Проверяем, активен ли пользователь
        if user_id not in user_states or not user_states[user_id].get('active', True):
            await update.message.reply_text("❌ Бот отключен. Для активации нажмите /start")
            return
        
        # Проверяем, инициализирован ли DeepSeek
        if deepseek is None:
            await update.message.reply_text(
                "❌ Сервис DeepSeek не инициализирован. "
                "Пожалуйста, проверьте настройки DEEPSEEK_API_KEY на Render."
            )
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
            "⏳ Это может занять несколько секунд."
        )
        
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
        logger.error(f"❌ Ошибка при обработке текстового запроса: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            f"❌ Произошла ошибка при поиске информации: {str(e)}\n\n"
            "Попробуйте переформулировать запрос или нажмите /start для перезапуска."
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stop"""
    user_id = update.effective_user.id
    logger.info(f"🛑 Пользователь {user_id} остановил бота")
    
    if user_id in user_states:
        user_states[user_id]['active'] = False
    
    await update.message.reply_text(
        "🛑 Бот отключен. Чтобы снова начать пользоваться, нажмите /start"
    )

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перезапуск бота"""
    user_id = update.effective_user.id
    logger.info(f"🔄 Пользователь {user_id} перезапустил бота")
    
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
    logger.error(f"❌ Глобальная ошибка: {context.error}")
    logger.error(traceback.format_exc())
    
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
