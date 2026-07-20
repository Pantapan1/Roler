from shared import *

@market_router.message(Command("buy"))
async def gm_market_buy(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /buy [ID]")
    user_id = message.from_user.id
    char_name = await get_character(user_id)
    if not char_name: return await message.answer("Создай персонажа!")
    item_id = int(command.args)
    item = await db_execute("SELECT item_name, price, quantity, rarity FROM market WHERE id = ?", (item_id,), fetchone=True)
    if not item or item[2] <= 0: return await message.answer("❌ Товар не найден или закончился.")
    name, price, qty, rarity = item
    gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if not gold or gold[0] < price: return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    await db_execute("UPDATE market SET quantity = quantity - 1 WHERE id = ?", (item_id,))
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + 1 WHERE user_id = ? AND item_name = ?", (user_id, name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, 1, ?)", (user_id, name, rarity))
    await message.answer(f"✅ Куплено: <b>{name}</b> за {price} золота!")

