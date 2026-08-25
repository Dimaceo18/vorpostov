import logging
import os
import sys
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# Добавляем текущую директорию в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

async def clear_webhook_and_start(application):
    """Очищаем webhook и запускаем polling"""
    try:
        # Пытаемся удалить webhook
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook очищен")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось очистить webhook: {e}")
    
    # Запускаем polling с явным указанием разрешенных обновлений
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )
    logger.info("🚀 Бот запущен и слушает обновления")
    
    # Держим бота запущенным
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main():
    """Основная функция запуска бота"""
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не найден")
        return
    
    logger.info(f"✅ TELEGRAM_TOKEN найден: {token[:10]}...")
    
    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    if not deepseek_key:
        logger.error("❌ DEEPSEEK_API_KEY не найден")
        return
    
    logger.info(f"✅ DEEPSEEK_API_KEY найден: {deepseek_key[:10]}...")
    
    try:
        # Создаем приложение
        application = Application.builder().token(token).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("restart", restart_command))
        application.add_handler(CommandHandler("stop", stop_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
        application.add_error_handler(error_handler)
        
        logger.info("🚀 Запускаем бота с очисткой webhook...")
        
        # Запускаем с очисткой webhook
        asyncio.run(clear_webhook_and_start(application))
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()
