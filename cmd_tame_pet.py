from shared import *

@admin_router.message(Command("tame_pet"))
async def tame_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /tame_pet [Название питомца]")
    
    user_id = message.from_user.id
    pet_name = command.args.strip()
    
    pet = await db_execute("SELECT id, name FROM pets WHERE name = ?", (pet_name,), fetchone=True)
    if not pet:
        return await message.answer("❌ Питомец не найден.")
    
    existing = await db_execute("SELECT 1 FROM player_pets WHERE user_id = ? AND pet_id = ?", (user_id, pet[0]), fetchone=True)
    if existing:
        return await message.answer("⚠️ У тебя уже есть этот питомец!")
    
    await db_execute("INSERT INTO player_pets (user_id, pet_id) VALUES (?, ?)", (user_id, pet[0]))
    await message.answer(f"✅ Ты приручил <b>{pet[1]}</b>! Смотри /my_pets")

