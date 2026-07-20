from shared import *

@admin_router.message(Command("feed_pet"))
async def feed_pet(message: types.Message, command: CommandObject):
    if not command.args:
        return await message.answer("Формат: /feed_pet [Название питомца] [Еда]")
    
    user_id = message.from_user.id
    args = command.args.split(maxsplit=1)
    if len(args) < 2:
        return await message.answer("Формат: /feed_pet [Название] [Еда]")
    
    pet_name, food_name = args[0], args[1]
    
    pet = await db_execute(
        "SELECT pp.id, pp.happiness FROM player_pets pp JOIN pets p ON pp.pet_id = p.id WHERE pp.user_id = ? AND p.name = ?",
        (user_id, pet_name), fetchone=True
    )
    if not pet:
        return await message.answer("❌ Питомец не найден.")
    
    food = await db_execute("SELECT happiness_boost, xp_boost, price FROM pet_items WHERE name = ?", (food_name,), fetchone=True)
    if not food:
        return await message.answer(f"❌ Еда <b>{food_name}</b> не найдена. Доступно: Обычный корм, Вкусняшка, Элитный корм")
    
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < food[2]:
        return await message.answer(f"❌ Недостаточно золота. Нужно {food[2]}.")
    
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (food[2], user_id))
    new_happiness = min(100, pet[1] + food[0])
    await db_execute("UPDATE player_pets SET happiness = ?, xp = xp + ? WHERE id = ?", (new_happiness, food[1], pet[0]))
    
    await message.answer(f"✅ {pet_name} покормлен! Счастье: {new_happiness}/100")

