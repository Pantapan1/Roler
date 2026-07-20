from shared import *

@market_router.message(Command("cancel_sale"))
async def cancel_sale(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /cancel_sale [ID лота]")
    
    user_id = message.from_user.id
    lot_id = int(command.args)
    
    lot = await db_execute("SELECT item_name, quantity, rarity FROM player_market WHERE id = ? AND seller_id = ? AND is_sold = 0", (lot_id, user_id), fetchone=True)
    if not lot:
        return await message.answer("❌ Лот не найден или уже продан.")
    
    item_name, quantity, rarity = lot
    
    # Возвращаем предмет
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (quantity, user_id, item_name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, quantity, rarity))
    
    # Удаляем лот
    await db_execute("DELETE FROM player_market WHERE id = ?", (lot_id,))
    
    await message.answer(f"✅ Лот <b>{item_name}</b> снят с продажи и возвращен в инвентарь.")

