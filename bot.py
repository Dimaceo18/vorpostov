import logging
import os
import sys
from dotenv import load_dotenv
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Импортируем обработчики
try:
    from handlers import (
        start_command,
        restart_command,
        button_handler,
        handle_text,
        stop_command,
        help_command,
        stats_command,
        error_handler,
        unknown_command
    )
    logger.info("✅ Модуль handlers успешно загружен")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта handlers: {e}")
    sys.exit(1)

def main():
    """Основная функция запуска бота"""
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден в переменных окружения")
        logger.info("Пожалуйста, создайте файл .env с переменной TELEGRAM_TOKEN")
        return
    
    try:
        # Создаем приложение
        application = ApplicationBuilder().token(token).build()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("restart", restart_command))
        application.add_handler(CommandHandler("stop", stop_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Регистрируем обработчик кнопок
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Регистрируем обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        # Регистрируем обработчик неизвестных команд
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
        
        # Регистрируем глобальный обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        logger.info("🚀 Бот с ИИ и поиском в интернете запущен!")
        logger.info(f"📱 Бот @{application.bot.username if hasattr(application.bot, 'username') else 'unknown'}")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()
