from shared import *

@admin_router.message(Command("open_loot"))
async def open_lootbox(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /open_loot [ID сундука]")
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    room_id = await get_user_room(user_id)
    box_id = int(command.args)
    
    box = await db_execute("SELECT name, price FROM loot_boxes WHERE id = ? AND is_active = 1", (box_id,), fetchone=True)
    if not box:
        return await message.answer("❌ Сундук не найден или неактивен.")
    
    name, price = box
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < price:
        return await message.answer(f" Недостаточно золота. Нужно {price}, есть {user_gold[0]}.")
    
    # Списываем золото
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    
    # Получаем предметы из сундука
    items = await db_execute("SELECT item_name, rarity, chance, quantity_min, quantity_max FROM loot_box_items WHERE box_id = ?", (box_id,), fetch=True)
    if not items:
        await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, user_id))
        return await message.answer("❌ Сундук пуст. Золото возвращено.")
    
    # Роллим лут
    received = []
    for item in items:
        item_name, rarity, chance, q_min, q_max = item
        if random.random() * 100 <= chance:
            qty = random.randint(q_min or 1, q_max or 1)
            existing = await db_execute("SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?", (user_id, item_name), fetchone=True)
            if existing:
                await db_execute("UPDATE inventory SET quantity = quantity + ? WHERE user_id = ? AND item_name = ?", (qty, user_id, item_name))
            else:
                await db_execute("INSERT INTO inventory (user_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?)", (user_id, item_name, qty, rarity))
            received.append(f"{RARITY_ICONS.get(rarity, '')} {item_name} x{qty}")
    
    char_name = await get_character(user_id) or "Неизвестный"
    if received:
        loot_text = "\n".join(received)
        msg = f"🎁 <b>{char_name}</b> открывает <b>{name}</b>!\n\n Получено:\n{loot_text}"
        await broadcast_to_session(chat_id, msg, room_id)
        await log_message(chat_id, "СИСТЕМА", msg, room_id)
    else:
        await message.answer(f"😢 Пусто... Попробуй ещё раз!")

