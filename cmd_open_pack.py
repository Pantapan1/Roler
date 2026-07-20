from shared import *

@admin_router.message(Command("open_pack"))
async def open_card_pack(message: types.Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /open_pack [ID пакета]")
    
    user_id = message.from_user.id
    pack_id = int(command.args)
    
    pack = await db_execute("SELECT name, price FROM card_packs WHERE id = ? AND is_active = 1", (pack_id,), fetchone=True)
    if not pack:
        return await message.answer(" Пакет не найден.")
    
    name, price = pack
    user_gold = await db_execute("SELECT gold FROM users WHERE user_id = ?", (user_id,), fetchone=True)
    if user_gold[0] < price:
        return await message.answer(f"❌ Недостаточно золота. Нужно {price}.")
    
    await db_execute("UPDATE users SET gold = gold - ? WHERE user_id = ?", (price, user_id))
    
    # Получаем карты
    cards = await db_execute("SELECT id, name, rarity, chance, stat_type, stat_value FROM cards WHERE pack_id = ?", (pack_id,), fetch=True)
    if not cards:
        await db_execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (price, user_id))
        return await message.answer(" Пакет пуст. Золото возвращено.")
    
    # Роллим 3 карты
    received = []
    for _ in range(3):
        total_chance = sum(c[2] for c in cards)
        roll = random.random() * total_chance
        current = 0
        selected = cards[0]
        for card in cards:
            current += card[2]
            if roll <= current:
                selected = card
                break
        
        card_id, card_name, rarity, _, stat_type, stat_value = selected
        
        # Добавляем в коллекцию
        existing = await db_execute("SELECT quantity FROM player_cards WHERE user_id = ? AND card_id = ?", (user_id, card_id), fetchone=True)
        if existing:
            await db_execute("UPDATE player_cards SET quantity = quantity + 1 WHERE user_id = ? AND card_id = ?", (user_id, card_id))
        else:
            await db_execute("INSERT INTO player_cards (user_id, card_id, quantity) VALUES (?, ?, 1)", (user_id, card_id))
        
        stat_text = f" [+{stat_value} {stat_type.upper()}]" if stat_type and stat_value else ""
        received.append(f"{RARITY_ICONS.get(rarity, '⚪')} <b>{card_name}</b>{stat_text}")
    
    char_name = await get_character(user_id) or "Неизвестный"
    cards_list = "\n".join(received)
    await message.answer(f"🃏 <b>{char_name}</b> открывает пакет <b>{name}</b>!\n\n🎴 Получено:\n{cards_list}")

