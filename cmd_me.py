from shared import *

@admin_router.message(Command("me"))
@player_router.message(Command("me"))
async def check_stats_card(message: types.Message):
    user_id = message.from_user.id
    user_data = await db_execute("SELECT character_name FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not user_data:
        return await message.answer("Сначала создай персонажа через /create")
    
    card = await generate_character_card(user_id)
    if card:
        await message.answer_photo(card, caption=f"👤 <b>{user_data[0]}</b>")
    else:
        await check_stats_text(message)

