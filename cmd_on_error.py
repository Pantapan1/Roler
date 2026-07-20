from shared import *

@dp.error()
async def on_error(event: types.ErrorEvent):
    print(f"❌ Ошибка: {event.exception}")
    try:
        update = event.update
        if update.message:
            await update.message.answer("⚠️ Техническая ошибка.")
    except Exception:
        pass
    return True

