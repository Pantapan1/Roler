from shared import *

@admin_router.message(Command("add_loot"))
async def add_loot_to_box(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 4:
        return await message.answer("Формат: /add_loot [ID сундука] [Предмет] [Редкость] [Шанс%]\nПример: /add_loot 1 Меч legendary 5")
    
    try:
        box_id = int(args[0])
        item_name = args[1]
        rarity = args[2].lower()
        chance = float(args[3])
        
        if rarity not in RARITY_COLORS:
            return await message.answer(f"❌ Недопустимая редкость. Варианты: {', '.join(RARITY_COLORS.keys())}")
        
        await db_execute(
            "INSERT INTO loot_box_items (box_id, item_name, rarity, chance) VALUES (?, ?, ?, ?)",
            (box_id, item_name, rarity, chance)
        )
        await message.answer(f"✅ Предмет <b>{item_name}</b> [{rarity}] добавлен в сундук с шансом {chance}%!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

