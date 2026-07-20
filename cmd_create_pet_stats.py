from shared import *

@admin_router.message(PetCreate.waiting_stats, F.text)
async def create_pet_stats(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        return
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("❌ Формат: [STR] [AGI] [INT]")
    
    try:
        str_s, agi_s, int_s = map(int, args[:3])
        data = await state.get_data()
        
        await db_execute(
            "INSERT INTO pets (name, description, rarity, base_str, base_agi, base_int) VALUES (?, ?, ?, ?, ?, ?)",
            (data['pet_name'], data['pet_desc'], data['pet_rarity'], str_s, agi_s, int_s)
        )
        await state.clear()
        await message.answer(f"✅ Питомец <b>{data['pet_name']}</b> создан!")
    except Exception as e:
        await message.answer(f" Ошибка: {e}")

