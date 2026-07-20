from shared import *

@admin_router.message(PetCreate.waiting_desc, F.text)
async def create_pet_desc(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pet_desc=message.text)
    await message.answer("Введи <b>редкость</b> (common/uncommon/rare/epic/legendary):")
    await state.set_state(PetCreate.waiting_rarity)

