from shared import *

@admin_router.message(Command("pet_items"))
async def list_pet_items(message: types.Message):
    items = await db_execute("SELECT name, description, happiness_boost, xp_boost, price FROM pet_items", fetch=True)
    if not items:
        return await message.answer("🍖 Еды для питомцев нет.")
    
    text = "🍖 <b>ЕДА ДЛЯ ПИТОМЦЕВ:</b>\n\n"
    for row in items:
        name, desc, happ, xp, price = row
        text += f"🔹 <b>{name}</b> — {price} золота\n   {desc}\n   ❤️ +{happ} счастья | ✨ +{xp} XP\n\n"
    
    text += "<i>Использовать: /feed_pet [Питомец] [Еда]</i>"
    await message.answer(text)

