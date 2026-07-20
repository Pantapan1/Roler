from shared import *

@admin_router.message(Command("create_lootbox"))
async def create_lootbox_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer(" Введи <b>название</b> сундука:")
    await state.set_state(LootBoxCreate.waiting_name)

