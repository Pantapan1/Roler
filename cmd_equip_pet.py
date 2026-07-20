from shared import *

@admin_router.message(Command("equip_pet"))
async def equip_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /equip_pet [Название питомца]")
    
    user_id = message.from_user.id
    pet_name = command.args.strip()
    
    # Снимаем со всех
    await db_execute("UPDATE player_pets SET is_equipped = 0 WHERE user_id = ?", (user_id,))
    
    # Надеваем на нужного
    pet = await db_execute(
        "SELECT pp.id FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ? AND p.name = ?",
        (user_id, pet_name), fetchone=True
    )
    if not pet:
        return await message.answer(" Питомец не найден.")
    
    await db_execute("UPDATE player_pets SET is_equipped = 1 WHERE id = ?", (pet[0],))
    await message.answer(f"✅ <b>{pet_name}</b> теперь твой спутник!")

