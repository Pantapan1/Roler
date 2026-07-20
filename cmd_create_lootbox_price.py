from shared import *

@admin_router.message(LootBoxCreate.waiting_price, F.text)
async def create_lootbox_price(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    try:
        price = int(message.text.strip())
        await state.update_data(box_price=price)
        await message.answer("Введи <b>описание</b> сундука:")
        await state.set_state(LootBoxCreate.waiting_items)
    except:
        await message.answer("❌ Введи число!")

