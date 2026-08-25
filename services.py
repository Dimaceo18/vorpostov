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
        """Новости - как в чате"""
        try:
            logger.info("📰 Запрос новостей...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                        Собери все свежие новости за сегодня {datetime.now().strftime('%d.%m.%Y')} по Беларуси и Минску.
                        Найди реальные, актуальные новости за последние 24 часа.
                        Дай 15 новостей с заголовками и ссылками на источники.
                        Если не можешь найти - скажи честно.
                        
                        Формат:
                        📌 ЗАГОЛОВОК
                        🔗 Ссылка
                        """
                    }
                ],
                temperature=0.3,
                max_tokens=2500,
                extra_body={"enable_search": True}
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ Получен ответ, длина: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return f"❌ Ошибка при поиске новостей: {str(e)[:200]}"
    
    async def generate_events_digest(self) -> str:
        """Афиша - как в чате"""
        try:
            logger.info("🎭 Запрос афиши...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                        Пришли мне афишу интересных мероприятий в Минске на сегодня {datetime.now().strftime('%d.%m.%Y')}.
                        Найди реальные, актуальные мероприятия.
                        Дай 10 мероприятий с названиями, местом, временем, стоимостью и ссылками.
                        Отметь ТОП-3 самых интересных.
                        Если не можешь найти - скажи честно, что не нашел.
                        """
                    }
                ],
                temperature=0.5,
                max_tokens=3000,
                extra_body={"enable_search": True}
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ Получен ответ, длина: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return f"❌ Ошибка при поиске афиши: {str(e)[:200]}"
    
    async def generate_weather_currency_digest(self) -> str:
        """Погода и курсы - как в чате"""
        try:
            logger.info("🌤️ Запрос погоды и курсов...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
                        Пришли мне прогноз погоды в Минске на сегодня {datetime.now().strftime('%d.%m.%Y')} и курс валют.
                        
                        1. Погода: температура, осадки, ветер, влажность, рекомендации
                        2. Курсы валют: USD, EUR, RUB к BYN
                        
                        Обязательно укажи источники (ссылку на сайт погоды и сайт НБ РБ).
                        """
                    }
                ],
                temperature=0.3,
                max_tokens=2000,
                extra_body={"enable_search": True}
            )
            
            result = response.choices[0].message.content
            result += f"\n\n🕐 Данные на {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            logger.info(f"✅ Получен ответ, длина: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return f"❌ Ошибка при поиске данных: {str(e)[:200]}"
    
    async def custom_query(self, query: str) -> str:
        """Произвольный запрос - как в чате"""
        try:
            logger.info(f"💬 Запрос: {query[:50]}...")
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=0.7,
                max_tokens=2500,
                extra_body={"enable_search": True}
            )
            
            result = response.choices[0].message.content
            logger.info(f"✅ Получен ответ, длина: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return f"❌ Ошибка: {str(e)[:200]}"
