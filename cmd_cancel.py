from shared import *

@admin_router.message(Command("cancel"))
@player_router.message(Command("cancel"))
@room_router.message(Command("cancel"))
@gacha_router.message(Command("cancel"))
@market_router.message(Command("cancel"))
@pets_router.message(Command("cancel"))
@cards_router.message(Command("cancel"))
async def cancel_any_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🛑 Действие отменено.")

