from shared import *

@market_router.message(Command("buy_market"))
async def buy_from_player_market(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /buy_market [ID лота]")
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    room_id = await get_user_room(user_id)
    lot_id = int(command.args)
    
    lot = await db_execute(
        "SELECT seller_id, item_name, price, quantity, rarity FROM player_market WHERE id = ? AND is_sold = 0",
        (lot_id,), fetchone=True
    )
    if not lot:
        return await message.answer("❌ Лот не найден или уже продан.")
    
    seller_id, item_name, price, quantity, rarity = lot
    
    if seller_id == user_id:
        return await message.answer("❌ Нельзя купить у себя!")
    
    buyer_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if buyer_gold[0] < price:
        return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    
    # Переводим золото
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, seller_id))
    
    # Добавляем предмет покупателю
    existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
    if existing:
        await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (quantity, user_id, item_name))
    else:
        await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, quantity, rarity))
    
    # Помечаем как проданное
    await db_execute("UPDATE player_market SET is_sold = 1 WHERE id = ?", (lot_id,))
    
    seller_name = await get_character(seller_id) or "Неизвестный"
    buyer_name = await get_character(user_id) or "Неизвестный"
    
    msg = f" <b>{buyer_name}</b> покупает <b>{item_name}</b> x{quantity} у <b>{seller_name}</b> за {price} золота!"
    await broadcast_to_session(chat_id, msg, room_id)
    await log_message(chat_id, "СИСТЕМА", msg, room_id)

