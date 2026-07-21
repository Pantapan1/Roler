from shared import *

@admin_router.message(Command("broadcast"))
async def broadcast_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await state.set_state(GMBroadcast.waiting_message)
    await message.answer("📢 Введи текст рассылки для ВСЕХ пользователей (можно с картинкой, подписью к ней) (или /cancel):")

