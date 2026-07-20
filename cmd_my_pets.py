from shared import *

@admin_router.message(Command("my_pets"))
async def my_pets(message: types.Message):
    user_id = message.from_user.id
    pets = await db_execute(
        "SELECT p.name, p.rarity, p.base_str, p.base_agi, p.base_int, pp.level, pp.xp, pp.happiness, pp.is_equipped "
        "FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ?",
        (user_id,), fetch=True
    )
    if not pets:
        return await message.answer(" У тебя нет питомцев. Смотри /pets")
    
    text = "🐕 <b>ТВОИ ПИТОМЦЫ:</b>\n\n"
    for row in pets:
        name, rarity, str_s, agi_s, int_s, level, xp, happiness, equipped = row
        eq_icon = "⚔️ " if equipped else ""
        happiness_icon = "😊" if happiness > 70 else "😐" if happiness > 30 else "😢"
        
        # Статы с учетом уровня
        total_str = str_s + (level - 1)
        total_agi = agi_s + (level - 1)
        total_int = int_s + (level - 1)
        
        text += f"{eq_icon}{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> (Ур. {level}) {happiness_icon}\n"
        text += f"   💪 {total_str} |  {total_agi} | 🧠 {total_int}\n"
        text += f"   ✨ XP: {xp}/100 | ❤️ Счастье: {happiness}/100\n\n"
    
    text += "<i>Экипировать: /equip_pet [Название]\nПокормить: /feed_pet [Название] [Еда]</i>"
    await message.answer(text)

