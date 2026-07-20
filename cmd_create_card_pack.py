from shared import *

@admin_router.message(Command("create_card_pack"))
async def create_card_pack_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🃏 Введи <b>название</b> пакета карт:")
    await state.set_state(CardPackCreate.waiting_name)

