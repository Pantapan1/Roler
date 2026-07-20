from shared import *

@room_router.message(Command("room_create"))
async def room_create_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if await get_user_room(user_id):
        return await message.answer("⚠️ Ты уже в комнате. Сначала /room_leave")
    await state.set_state(RoomCreate.waiting_name)
    await message.answer("🏠 Введи название новой комнаты (или /cancel):")

