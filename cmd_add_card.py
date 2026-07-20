from shared import *

@admin_router.message(Command("add_card"))
async def add_card_to_pack(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 5:
        return await message.answer("Формат: /add_card [ID пакета] [Название] [Редкость] [Шанс%] [Тип стата] [Значение]\nТипы: str/agi/int/none")
    
    try:
        pack_id = int(args[0])
        name = args[1]
        rarity = args[2].lower()
        chance = float(args[3])
        stat_type = args[4].lower() if len(args) > 4 else 'none'
        stat_value = int(args[5]) if len(args) > 5 else 0
        
        if rarity not in RARITY_COLORS:
            return await message.answer(f"❌ Недопустимая редкость.")
        if stat_type not in ['str', 'agi', 'int', 'none']:
            return await message.answer("❌ Тип стата: str/agi/int/none")
        
        await db_execute(
            "INSERT INTO cards (pack_id, name, rarity, chance, stat_type, stat_value) VALUES (?, ?, ?, ?, ?, ?)",
            (pack_id, name, rarity, chance, stat_type if stat_type != 'none' else None, stat_value)
        )
        await message.answer(f"✅ Карта <b>{name}</b> [{rarity}] добавлена!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

