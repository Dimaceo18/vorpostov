import logging
from openai import AsyncOpenAI
from datetime import datetime
import asyncio
import traceback

logger = logging.getLogger(__name__)

class DeepSeekService:
    """Сервис для работы с DeepSeek API с поддержкой поиска в интернете"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        try:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=120.0  # Увеличиваем таймаут
            )
            logger.info("✅ DeepSeek клиент создан")
        except Exception as e:
            logger.error(f"❌ Ошибка создания DeepSeek клиента: {e}")
            raise
        
        self.search_enabled = True
        logger.info("✅ DeepSeek сервис инициализирован")
    
    async def generate_news_digest(self) -> str:
        """Генерация дайджеста новостей через поиск DeepSeek"""
        try:
            logger.info("📰 Начинаем поиск новостей...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - помощник, который составляет дайджест новостей для жителей Минска и Беларуси.
            Сегодня {current_date}.
            
            Задача: Найди в интернете и составь дайджест самых важных новостей за последние 24 часа 
            по Беларуси и Минску.
            
            Требования к ответу:
            1. Найди 5-7 самых важных новостей
            2. Каждую новость опиши кратко (2-3 предложения)
            3. Добавь ссылки на источники
            4. Выдели самую важную новость в начале
            5. Сгруппируй по темам, если нужно
            6. Оформи красиво с эмодзи 📰
            
            Важно:
            - Используй ТОЛЬКО актуальные новости за последние 24 часа
            - Проверяй достоверность информации
            - Пиши на русском языке
            - Будь объективным и нейтральным
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации дайджеста новостей: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске новостей: {str(e)}"
    
    async def generate_events_digest(self) -> str:
        """Генерация дайджеста мероприятий через поиск DeepSeek"""
        try:
            logger.info("🎭 Начинаем поиск мероприятий...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - культурный гид по Минску. Сегодня {current_date}.
            
            Задача: Найди в интернете и составь афишу самых интересных мероприятий в Минске на сегодня.
            
            Требования к ответу:
            1. Найди 6-8 мероприятий на сегодня
            2. Для каждого укажи: название, время, место, стоимость
            3. Добавь краткое описание каждого мероприятия
            4. Сгруппируй по категориям
            5. Отметь самые интересные события
            6. Добавь практические советы
            
            Оформи красиво с эмодзи 🎭.
            
            Важно:
            - Используй ТОЛЬКО мероприятия на СЕГОДНЯ
            - Проверяй актуальность информации
            - Пиши на русском языке
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации дайджеста мероприятий: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске мероприятий: {str(e)}"
    
    async def generate_weather_currency_digest(self) -> str:
        """Генерация сводки погоды и курсов валют через поиск DeepSeek"""
        try:
            logger.info("🌤️ Начинаем поиск погоды и курсов...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - помощник, который составляет сводку погоды и курсов валют для Минска.
            Сегодня {current_date}.
            
            Задача: Найди в интернете актуальную информацию:
            1. Прогноз погоды в Минске на сегодня
            2. Курсы валют (USD, EUR, RUB) от Национального банка Беларуси
            
            Требования к ответу:
            1. Погода: температура, осадки, ветер, рекомендации
            2. Курсы валют: текущие курсы, изменения
            
            Оформи красиво с эмодзи 🌤️.
            
            Важно:
            - Используй ТОЛЬКО актуальные данные на сегодня
            - Проверяй информацию из надежных источников
            - Пиши на русском языке
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1800,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации сводки погоды и курсов: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске данных: {str(e)}"
    
    async def custom_query(self, query: str) -> str:
        """Обработка произвольного запроса пользователя с поиском"""
        try:
            logger.info(f"💬 Обработка запроса: {query[:50]}...")
            
            prompt = f"""
            Пользователь спрашивает: {query}
            
            Найди в интернете актуальную информацию и дай подробный ответ.
            Ответ должен быть:
            1. Информативным и полным
            2. Основанным на актуальных данных
            3. Структурированным и легко читаемым
            4. С указанием источников
            5. На русском языке
            
            Если информация касается Минска или Беларуси - удели этому особое внимание.
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке запроса: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске информации: {str(e)}"
