import asyncio
from telethon import TelegramClient

# Ваши данные из Render
API_ID = 1234567  # Замените на ваш API_ID
API_HASH = "a1b2c3d4e5f6..."  # Замените на ваш API_HASH
PHONE_NUMBER = "+71234567890"  # Замените на ваш номер

async def main():
    client = TelegramClient('session_name', API_ID, API_HASH)
    
    try:
        await client.start(phone=PHONE_NUMBER)
        print("✅ Сессия успешно создана!")
        
        # Получаем строку сессии
        session_string = client.session.save()
        print("\n📌 СКОПИРУЙТЕ ЭТУ СТРОКУ:")
        print("=" * 50)
        print(session_string)
        print("=" * 50)
        print("\n✅ Добавьте эту строку в Render как SESSION_STRING")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
