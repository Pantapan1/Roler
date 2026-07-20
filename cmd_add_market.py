from shared import *

@admin_router.message(Command("add_market"))
async def add_market_item(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args or "-" not in command.args:
        return await message.answer("Формат: /add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]")
    head, rest = command.args.split("-", 1)
    head_parts = head.split(maxsplit=2)
    if len(head_parts) < 3 or not head_parts[0].isdigit() or not head_parts[1].isdigit():
        return await message.answer("Формат: /add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]")
    qty, price, name = int(head_parts[0]), int(head_parts[1]), head_parts[2].strip()
    rest_parts = rest.strip().rsplit(maxsplit=1)
    if len(rest_parts) == 2 and rest_parts[1].lower() in RARITY_NAMES:
        desc, rarity = rest_parts[0].strip(), rest_parts[1].lower()
    else:
        desc, rarity = rest.strip(), "common"
    await db_execute("INSERT INTO market (item_name, price, description, quantity, rarity) VALUES (?, ?, ?, ?, ?)", (name, price, desc, qty, rarity))
    await message.answer(f"✅ <b>{name}</b> добавлен на рынок ГМа: {price} золота x{qty}")

