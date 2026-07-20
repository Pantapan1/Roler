from shared import *

@admin_router.message(CardPackCreate.waiting_price, F.text)
async def create_card_pack_price(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    try:
        price = int(message.text.strip())
        await state.update_data(pack_price=price)
        await message.answer("Введи <b>описание</b> пакета:")
        await state.set_state(CardPackCreate.waiting_cards)
    except:
        await message.answer("❌ Введи число!")

