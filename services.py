import logging
from openai import AsyncOpenAI
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)

class DeepSeekService:
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=120.0,
                max_retries=3
            )
            logger.info("✅ DeepSeek клиент создан")
        except Exception as e:
            logger.error(f"❌ Ошибка создания клиента: {e}")
            raise
    
    async def generate_news_digest(self) -> str:
        """Генерация дайджеста новостей с включенным поиском"""
        try:
            logger.info("📰 Начинаем поиск новостей...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - новостной агрегатор. Твоя задача - собирать САМЫЕ СВЕЖИЕ новости за последние 24 часа."
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Найди 15 САМЫХ СВЕЖИХ новостей за последние 24 часа по Беларуси и Минску.
                        Сегодня {datetime.now().strftime('%d.%m.%Y')}, время {datetime.now().strftime('%H:%M')}.
                        
                        ВАЖНО: Используй ТОЛЬКО новости за последние 24 часа!
                        Используй поиск в интернете для получения актуальной информации!
                        
                        Формат для КАЖДОЙ новости (строго):
                        📌 ЗАГОЛОВОК НОВОСТИ
                        🔗 Ссылка на источник
                        
                        Требования:
                        1. 15 самых свежих новостей
                        2. Только заголовок + ссылка
                        3. Без описаний и комментариев
                        4. Сортировка от самой свежей к более старым
                        """
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                extra_body={"enable_search": True}  # <-- ЭТО КЛЮЧЕВОЙ ПАРАМЕТР!
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ Получен ответ от DeepSeek API, длина: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка при генерации новостей: {error_msg}")
            logger.error(traceback.format_exc())
            return f"❌ Ошибка при поиске новостей: {error_msg[:200]}"
    
    async def generate_events_digest(self) -> str:
        """Генерация афиши мероприятий с поиском"""
        try:
            logger.info("🎭 Начинаем поиск мероприятий...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - культурный гид по Минску. Ищешь ТОЛЬКО актуальные мероприятия на сегодня."
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Найди 10 САМЫХ ИНТЕРЕСНЫХ мероприятий в Минске на СЕГОДНЯ ({datetime.now().strftime('%d.%m.%Y')}).
                        
                        ВАЖНО: Используй поиск в интернете для получения актуальной информации!
                        Только мероприятия, которые проходят СЕГОДНЯ!
                        
                        Формат для КАЖДОГО мероприятия:
                        🎯 НАЗВАНИЕ
                        📍 Место: [название места]
                        🕐 Время: [время начала]
                        💰 Стоимость: [цена]
                        📝 Краткое описание (1 предложение)
                        🔗 Ссылка: [URL]
                        
                        Отметь ТОП-3 самых интересных события знаком ⭐
                        """
                    }
                ],
                temperature=0.8,
                max_tokens=2500,
                extra_body={"enable_search": True}  # <-- ЭТО КЛЮЧЕВОЙ ПАРАМЕТР!
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ Получен ответ от DeepSeek API, длина: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка при генерации афиши: {error_msg}")
            logger.error(traceback.format_exc())
            return f"❌ Ошибка при поиске мероприятий: {error_msg[:200]}"
    
    async def generate_weather_currency_digest(self) -> str:
        """Генерация сводки погоды и курсов валют с поиском"""
        try:
            logger.info("🌤️ Начинаем поиск погоды и курсов...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - информационный помощник. Ищешь ТОЛЬКО САМЫЕ СВЕЖИЕ данные о погоде и курсах валют."
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Найди САМУЮ СВЕЖУЮ информацию на СЕГОДНЯ ({datetime.now().strftime('%d.%m.%Y')}, {datetime.now().strftime('%H:%M')}):
                        
                        1. ПОГОДА В МИНСКЕ:
                           - Температура сейчас
                           - Прогноз на день (макс/мин)
                           - Осадки
                           - Ветер
                           - Рекомендации
                           - ИСТОЧНИК: [ссылка]
                        
                        2. КУРСЫ ВАЛЮТ (НБ РБ):
                           - USD/BYN
                           - EUR/BYN
                           - RUB/BYN
                           - ИСТОЧНИК: [ссылка на сайт НБ РБ]
                        
                        ВАЖНО: Используй поиск в интернете для получения актуальных данных!
                        """
                    }
                ],
                temperature=0.3,
                max_tokens=1500,
                extra_body={"enable_search": True}  # <-- ЭТО КЛЮЧЕВОЙ ПАРАМЕТР!
            )
            
            result = response.choices[0].message.content
            result += f"\n\n🕐 Данные обновлены: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            logger.info(f"✅ Получен ответ от DeepSeek API, длина: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка при генерации сводки: {error_msg}")
            logger.error(traceback.format_exc())
            return f"❌ Ошибка при поиске данных: {error_msg[:200]}"
    
    async def custom_query(self, query: str) -> str:
        """Обработка произвольного запроса с поиском"""
        try:
            logger.info(f"💬 Обработка запроса: {query[:50]}...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - помощник, который ищет свежую информацию в интернете. Всегда указывай источники."
                    },
                    {
                        "role": "user",
                        "content": f"""
                        Пользователь спрашивает: {query}
                        
                        Найди САМУЮ СВЕЖУЮ информацию в интернете.
                        Используй поиск в интернете для получения актуальных данных!
                        
                        Требования:
                        1. Только актуальные данные
                        2. Указывай источники (ссылки)
                        3. Ответ структурированный и понятный
                        4. На русском языке
                        """
                    }
                ],
                temperature=0.7,
                max_tokens=2000,
                extra_body={"enable_search": True}  # <-- ЭТО КЛЮЧЕВОЙ ПАРАМЕТР!
            )
            
            result = response.choices[0].message.content
            result += f"\n\n🕐 Данные обновлены: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            logger.info(f"✅ Получен ответ от DeepSeek API, длина: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Ошибка при обработке запроса: {error_msg}")
            logger.error(traceback.format_exc())
            return f"❌ Ошибка при поиске информации: {error_msg[:200]}"
