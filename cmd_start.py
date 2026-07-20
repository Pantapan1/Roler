from shared import *

@admin_router.message(Command("start", "create"))
@player_router.message(Command("start", "create"))
async def cmd_create_char(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    existing = await get_character(user_id)
    if existing:
        await message.answer(f"⚠️ У тебя уже есть персонаж: <b>{existing}</b>.\nСоздание нового сбросит статы.\nВведи имя нового героя или /cancel:")
    else:
        await message.answer("📝 Введи <b>Имя</b> своего героя:")
    await state.set_state(RPState.register_name)

