from shared import *

@admin_router.message(Command("create_pet"))
async def create_pet_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🐾 Введи <b>название</b> питомца:")
    await state.set_state(PetCreate.waiting_name)

