from shared import *

@admin_router.message(RPState.register_name, F.text)
@player_router.message(RPState.register_name, F.text)
async def register_name(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    await state.update_data(char_name=message.text.strip())
    await message.answer(f"Имя: <b>{message.text}</b>!\nТеперь опиши свой <b>Класс и биографию</b>:")
    await state.set_state(RPState.register_bio)

