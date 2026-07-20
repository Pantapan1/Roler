from shared import *

@admin_router.message(LootBoxCreate.waiting_items, F.text)
async def create_lootbox_items(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    name = data['box_name']
    price = data['box_price']
    desc = message.text
    
    await db_execute(
        "INSERT INTO loot_boxes (name, price, description) VALUES (?, ?, ?)",
        (name, price, desc)
    )
    await state.clear()
    await message.answer(f"✅ Сундук <b>{name}</b> создан за {price} золота!\nТеперь добавь предметы: <code>/add_loot [ID] [Предмет] [Редкость] [Шанс%]</code>")

