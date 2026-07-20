from shared import *

@admin_router.message(Command("fav_card"))
async def favorite_card(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /fav_card [Название карты]")
    
    user_id = message.from_user.id
    card_name = command.args.strip()
    
    card = await db_execute(
        "SELECT pc.id FROM player_cards pc JOIN cards c ON pc.card_id = c.id WHERE pc.user_id = ? AND c.name = ?",
        (user_id, card_name), fetchone=True
    )
    if not card:
        return await message.answer("❌ Карта не найдена.")
    
    current = await db_execute("SELECT is_favorite FROM player_cards WHERE id = ?", (card[0],), fetchone=True)
    await db_execute("UPDATE player_cards SET is_favorite = ? WHERE id = ?", (not current[0], card[0]))
    status = "добавлена" if not current[0] else "убрана"
    await message.answer(f"✅ Карта {status} в избранное!")

