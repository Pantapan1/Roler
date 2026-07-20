from shared import *

@market_router.message(Command("sell"))
async def player_sell_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name:
        return await message.answer("Создай персонажа!")
    
    if not command.args:
        return await message.answer("Формат: /sell [Название предмета] [Цена]")
    
    args = command.args.rsplit(maxsplit=1)
    if len(args) < 2:
        return await message.answer("Формат: /sell [Предмет] [Цена]")
    
    item_name, price_str = args[0], args[1]
    try:
        price = int(price_str)
    except:
        return await message.answer(" Цена должна быть числом!")
    
    # Проверяем наличие
    item = await db_execute("SELECT quantity, rarity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if not item or item[0] <= 0:
        return await message.answer(f"❌ У тебя нет предмета <b>{item_name}</b>.")
    
    quantity, rarity = item
    
    # Создаем лот
    await db_execute(
        "INSERT INTO player_market (seller_id, item_name, price, quantity, rarity) VALUES (?, ?, ?, ?, ?)",
        (user_id, item_name, price, quantity, rarity)
    )
    
    # Удаляем из инвентаря
    await db_execute("DELETE FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name))
    
    await message.answer(f"✅ <b>{item_name}</b> выставлен на продажу за {price} золота!")

