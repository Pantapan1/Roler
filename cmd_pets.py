from shared import *

@admin_router.message(Command("pets"))
async def list_pets(message: types.Message):
    pets = await db_execute("SELECT name, description, rarity, base_str, base_agi, base_int, max_level FROM pets", fetch=True)
    if not pets:
        return await message.answer("🐾 Питомцев пока нет.")
    
    text = "🐾 <b>ДОСТУПНЫЕ ПИТОМЦЫ:</b>\n\n"
    for row in pets:
        name, desc, rarity, str_s, agi_s, int_s, max_lvl = row
        text += f"{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> [{RARITY_NAMES.get(rarity, 'Обычный')}]\n"
        text += f"   💪 {str_s} | 🏃 {agi_s} |  {int_s}\n"
        text += f"   Макс. уровень: {max_lvl}\n"
        text += f"   <i>{desc}</i>\n\n"
    
    text += "<i>Приручить: /tame_pet [Название]</i>"
    await message.answer(text)

