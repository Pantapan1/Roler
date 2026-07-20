from shared import *

@admin_router.message(CardPackCreate.waiting_cards, F.text)
async def create_card_pack_cards(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    data = await state.get_data()
    name = data['pack_name']
    price = data['pack_price']
    desc = message.text
    
    await db_execute(
        "INSERT INTO card_packs (name, price, description) VALUES (?, ?, ?)",
        (name, price, desc)
    )
    await state.clear()
    await message.answer(f"✅ Пакет <b>{name}</b> создан!\nДобавь карты: <code>/add_card [ID пакета] [Название] [Редкость] [Шанс%] [Тип стата] [Значение]</code>")

