import logging
import os
import sys
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

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
    logger.info("✅ Модуль handlers загружен")
except ImportError as e:
    logger.error(f"❌ Ошибка импорта handlers: {e}")
    sys.exit(1)

def main():
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден")
        return
    
    logger.info(f"✅ TELEGRAM_TOKEN: {token[:10]}...")
    
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if not deepseek_key:
        logger.error("❌ DEEPSEEK_API_KEY не найден")
        return
    
    logger.info(f"✅ DEEPSEEK_API_KEY: {deepseek_key[:10]}...")
    
    try:
        application = Application.builder().token(token).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("restart", restart_command))
        application.add_handler(CommandHandler("stop", stop_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
        application.add_error_handler(error_handler)
        
        logger.info("🚀 Бот запущен!")
        application.run_polling(allowed_updates=['message', 'callback_query'])
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == '__main__':
    main()
