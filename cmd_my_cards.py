from shared import *

@admin_router.message(Command("my_cards"))
async def my_cards_collection(message: types.Message):
    user_id = message.from_user.id
    cards = await db_execute(
        "SELECT c.name, c.rarity, c.description, c.stat_type, c.stat_value, pc.quantity, pc.is_favorite "
        "FROM player_cards pc JOIN cards c ON pc.card_id = c.id WHERE pc.user_id = ? ORDER BY c.rarity DESC, c.name",
        (user_id,), fetch=True
    )
    if not cards:
        return await message.answer(" У тебя нет карт. Открой пакеты через /cards")
    
    text = "📖 <b>ТВОЯ КОЛЛЕКЦИЯ:</b>\n\n"
    for row in cards:
        name, rarity, desc, stat_type, stat_value, qty, fav = row
        fav_icon = "⭐ " if fav else ""
        stat_text = f" [+{stat_value} {stat_type.upper()}]" if stat_type and stat_value else ""
        text += f"{fav_icon}{RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b> x{qty}{stat_text}\n<i>{desc[:60]}...</i>\n\n"
    
    text += "<i>Избранное: /fav_card [Название]</i>"
    await message.answer(text)

