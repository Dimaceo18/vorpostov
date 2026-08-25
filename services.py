import logging
from openai import AsyncOpenAI
from typing import Dict, List, Optional
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class DeepSeekService:
    """Сервис для работы с DeepSeek API с поддержкой поиска в интернете"""
    
    def __init__(self, api_key: str, base_url: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.search_enabled = True  # Включаем поиск по умолчанию
    
    async def generate_news_digest(self) -> str:
        """Генерация дайджеста новостей через поиск DeepSeek"""
        try:
            current_date = datetime.now().strftime("%d.%m.%Y")
            current_time = datetime.now().strftime("%H:%M")
            
            prompt = f"""
            Ты - помощник, который составляет дайджест новостей для жителей Минска и Беларуси.
            Сегодня {current_date}, текущее время {current_time}.
            
            Задача: Найди в интернете и составь дайджест самых важных новостей за последние 24 часа 
            (с {datetime.now().strftime('%d.%m.%Y')}) по Беларуси и Минску.
            
            Требования к ответу:
            1. Найди 5-7 самых важных новостей
            2. Каждую новость опиши кратко (2-3 предложения)
            3. Добавь ссылки на источники
            4. Выдели самую важную новость в начале
            5. Сгруппируй по темам, если нужно (политика, экономика, общество, спорт и т.д.)
            6. Оформи красиво с эмодзи 📰
            
            Важно:
            - Используй ТОЛЬКО актуальные новости за последние 24 часа
            - Проверяй достоверность информации
            - Пиши на русском языке
            - Будь объективным и нейтральным
            """
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                stream=False,
                extra_body={
                    "enable_search": True  # Включаем поиск в интернете
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка при генерации дайджеста новостей: {e}")
            return f"❌ Извините, произошла ошибка при поиске новостей: {str(e)}\n\nПопробуйте позже."
    
    async def generate_events_digest(self) -> str:
        """Генерация дайджеста мероприятий через поиск DeepSeek"""
        try:
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - культурный гид по Минску. Сегодня {current_date}.
            
            Задача: Найди в интернете и составь афишу самых интересных мероприятий в Минске на сегодня.
            
            Требования к ответу:
            1. Найди 6-8 мероприятий на сегодня (концерты, выставки, спектакли, кино, фестивали и т.д.)
            2. Для каждого укажи: название, время, место, стоимость билетов (если есть)
            3. Добавь краткое описание каждого мероприятия
            4. Сгруппируй по категориям (концерты, театры, выставки, кино, другое)
            5. Отметь самые интересные события, которые стоит посетить обязательно
            6. Добавь практические советы (как добраться, где купить билеты)
            
            Оформи красиво с эмодзи 🎭 и структурируй ответ.
            
            Важно:
            - Используй ТОЛЬКО мероприятия, которые проходят СЕГОДНЯ
            - Проверяй актуальность информации (время, место)
            - Пиши на русском языке
            """
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка при генерации дайджеста мероприятий: {e}")
            return f"❌ Извините, произошла ошибка при поиске мероприятий: {str(e)}\n\nПопробуйте позже."
    
    async def generate_weather_currency_digest(self) -> str:
        """Генерация сводки погоды и курсов валют через поиск DeepSeek"""
        try:
            current_date = datetime.now().strftime("%d.%m.%Y")
            
            prompt = f"""
            Ты - помощник, который составляет сводку погоды и курсов валют для Минска.
            Сегодня {current_date}.
            
            Задача: Найди в интернете актуальную информацию:
            1. Прогноз погоды в Минске на сегодня
            2. Курсы валют (USD, EUR, RUB) от Национального банка Беларуси на сегодня
            
            Требования к ответу:
            1. Погода:
               - Температура сейчас, днем, ночью
               - Осадки, ветер, влажность
               - Восход и закат
               - Рекомендации (что надеть, брать зонт и т.д.)
            
            2. Курсы валют:
               - Текущие курсы USD, EUR, RUB к BYN
               - Изменения за последние сутки (вырос/упал)
               - Прогноз или рекомендации (если есть данные)
            
            Оформи красиво с эмодзи 🌤️ и структурируй ответ.
            
            Важно:
            - Используй ТОЛЬКО актуальные данные на сегодня
            - Проверяй информацию из надежных источников
            - Пиши на русском языке
            - Дай практические рекомендации
            """
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1800,
                extra_body={
                    "enable_search": True
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка при генерации сводки погоды и курсов: {e}")
            return f"❌ Извините, произошла ошибка при поиске данных: {str(e)}\n\nПопробуйте позже."
    
    async def custom_query(self, query: str) -> str:
        """Обработка произвольного запроса пользователя с поиском"""
        try:
            prompt = f"""
            Пользователь спрашивает: {query}
            
            Найди в интернете актуальную информацию и дай подробный ответ.
            Ответ должен быть:
            1. Информативным и полным
            2. Основанным на актуальных данных
            3. Структурированным и легко читаемым
            4. С указанием источников (где это возможно)
            5. На русском языке
            
            Если информация касается Минска или Беларуси - удели этому особое внимание.
            """
            
            response = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
                extra_body={
                    "enable_search": True
                }
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {e}")
            return f"❌ Извините, произошла ошибка при поиске информации: {str(e)}"
