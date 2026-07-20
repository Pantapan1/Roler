from shared import *

@admin_router.message(RPState.register_bio, F.text)
@player_router.message(RPState.register_bio, F.text)
async def register_bio(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    char_name = data.get("char_name")
    bio = message.text
    user_id = message.from_user.id
    
    old_inv = await db_execute("SELECT item_name, quantity, is_equipped, rarity FROM inventory WHERE user_id = ?", (user_id,), fetch=True)
    
    await db_execute(
        "INSERT OR REPLACE INTO users (user_id, character_name, bio, hp, max_hp, xp, level, is_gm, gold, strength, agility, intelligence) "
        "VALUES (?, ?, ?, 100, 100, 0, 1, ?, 0, 0, 0, 0)",
        (user_id, char_name, bio, 1 if await is_admin(user_id) else 0)
    )
    
    for item in old_inv:
        await db_execute(
            "INSERT OR REPLACE INTO inventory (user_id, item_name, quantity, is_equipped, rarity) VALUES (?, ?, ?, ?, ?)",
            (user_id, item[0], item[1], item[2], item[3])
        )
    
    await message.answer(f"✅ Персонаж <b>{char_name}</b> создан!")
    await state.clear()

