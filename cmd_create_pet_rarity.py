from shared import *

@admin_router.message(PetCreate.waiting_rarity, F.text)
async def create_pet_rarity(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    rarity = message.text.lower().strip()
    if rarity not in RARITY_COLORS:
        return await message.answer("❌ Недопустимая редкость.")
    await state.update_data(pet_rarity=rarity)
    await message.answer("Введи <b>базовые статы</b> в формате: [STR] [AGI] [INT]\nПример: 5 3 2")
    await state.set_state(PetCreate.waiting_stats)

