from shared import *

@admin_router.message(CardPackCreate.waiting_name, F.text)
async def create_card_pack_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pack_name=message.text.strip())
    await message.answer("Введи <b>цену</b> пакета:")
    await state.set_state(CardPackCreate.waiting_price)

