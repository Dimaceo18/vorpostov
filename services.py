import logging
from openai import AsyncOpenAI
from datetime import datetime
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
                timeout=120.0
            )
            logger.info("✅ DeepSeek клиент создан")
        except Exception as e:
            logger.error(f"❌ Ошибка создания DeepSeek клиента: {e}")
            raise
        
        logger.info("✅ DeepSeek сервис инициализирован")
    
    async def generate_news_digest(self) -> str:
        """Генерация дайджеста новостей с ссылками"""
        try:
            logger.info("📰 Начинаем поиск новостей...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - новостной агрегатор для жителей Минска и Беларуси. Сегодня {current_date}.
            
            Задача: Найди в интернете 7-10 САМЫХ ВАЖНЫХ новостей за последние 24 часа по Беларуси и Минску.
            
            Требования к ответу:
            1. Каждая новость должна быть с заголовком и кратким описанием (2-3 предложения)
            2. ОБЯЗАТЕЛЬНО прикрепи ссылку на оригинальную новость (URL)
            3. Отсортируй по важности (самая важная - первая)
            4. Сгруппируй по темам: политика, экономика, общество, спорт, культура
            5. В начале дай краткую сводку (1-2 предложения о главном событии дня)
            6. Оформи красиво с эмодзи 📰
            
            Формат каждой новости:
            🔹 [Заголовок]
            📝 [Краткое описание]
            🔗 [Ссылка]
            
            Важно:
            - Используй ТОЛЬКО новости за последние 24 часа
            - Проверяй, чтобы ссылки были рабочими
            - Пиши на русском языке
            - Будь объективным
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2500,
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
        """Генерация афиши мероприятий"""
        try:
            logger.info("🎭 Начинаем поиск мероприятий...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - культурный гид по Минску. Сегодня {current_date}.
            
            Задача: Найди в интернете АКТУАЛЬНУЮ афишу мероприятий в Минске на СЕГОДНЯ.
            
            Найди 8-10 мероприятий разных категорий:
            - Концерты
            - Театры (спектакли)
            - Выставки
            - Кино (новинки)
            - Фестивали
            - Детские мероприятия
            - Спортивные события
            
            Для каждого мероприятия укажи:
            🎯 Название
            📍 Место проведения
            🕐 Время
            💰 Стоимость билетов (если есть информация)
            📝 Краткое описание (1-2 предложения)
            🔗 Ссылка на источник
            
            Отметь ТОП-3 самых интересных события.
            Добавь практические советы: как добраться, где купить билеты.
            
            Оформи красиво с эмодзи 🎭.
            
            Важно:
            - Используй ТОЛЬКО мероприятия на СЕГОДНЯ
            - Проверяй актуальность информации
            - Пиши на русском языке
            - Давай конкретные рекомендации
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2500,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации афиши: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске мероприятий: {str(e)}"
    
    async def generate_weather_currency_digest(self) -> str:
        """Генерация сводки погоды и курсов валют"""
        try:
            logger.info("🌤️ Начинаем поиск погоды и курсов...")
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - информационный помощник по Минску. Сегодня {current_date}.
            
            Задача: Найди в интернете актуальную информацию:
            
            1. ПРОГНОЗ ПОГОДЫ в Минске на сегодня:
               - Температура сейчас и в течение дня
               - Осадки (вероятность, тип)
               - Ветер (скорость, направление)
               - Влажность
               - Восход и закат
               - Рекомендации: что надеть, брать ли зонт
               
            2. КУРСЫ ВАЛЮТ от Национального банка Беларуси на сегодня:
               - USD/BYN
               - EUR/BYN  
               - RUB/BYN
               - Изменения за последние сутки (вырос/упал)
               - Краткий комментарий по ситуации на валютном рынке
            
            Оформи красиво:
            🌤️ Погода на сегодня
            💱 Курсы валют
            
            Добавь полезные советы и рекомендации.
            
            Важно:
            - Используй ТОЛЬКО актуальные данные на сегодня
            - Проверяй информацию из официальных источников
            - Пиши на русском языке
            """
            
            logger.info("📤 Отправляем запрос в DeepSeek API...")
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            logger.info("✅ Получен ответ от DeepSeek API")
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации сводки: {e}")
            logger.error(traceback.format_exc())
            return f"❌ Извините, произошла ошибка при поиске данных: {str(e)}"
    
    async def custom_query(self, query: str) -> str:
        """Обработка произвольного запроса пользователя"""
        try:
            logger.info(f"💬 Обработка запроса: {query[:50]}...")
            
            prompt = f"""
            Пользователь спрашивает: {query}
            
            Найди в интернете актуальную информацию и дай подробный ответ.
            
            Требования:
            1. Ответ должен быть информативным и полным
            2. Основан на актуальных данных
            3. Структурирован и легко читаем
            4. С указанием источников (ссылки)
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
