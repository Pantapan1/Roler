from shared import *

@admin_router.message(LootBoxCreate.waiting_name, F.text)
async def create_lootbox_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(box_name=message.text.strip())
    await message.answer("Введи <b>цену</b> сундука в золоте:")
    await state.set_state(LootBoxCreate.waiting_price)

