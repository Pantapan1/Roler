from shared import *

@admin_router.message(PetCreate.waiting_name, F.text)
async def create_pet_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(pet_name=message.text.strip())
    await message.answer("Введи <b>описание</b> питомца:")
    await state.set_state(PetCreate.waiting_desc)

