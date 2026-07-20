from shared import *

@admin_router.message(Command("add_pet_stat"))
async def add_pet_stat(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = command.args.split() if command.args else []
    if len(args) < 4:
        return await message.answer("Формат: /add_pet_stat [Название питомца] [STR] [AGI] [INT]")
    
    try:
        name = args[0]
        str_s, agi_s, int_s = map(int, args[1:4])
        await db_execute(
            "UPDATE pets SET base_str=?, base_agi=?, base_int=? WHERE name=?",
            (str_s, agi_s, int_s, name)
        )
        await message.answer(f"✅ Статы питомца <b>{name}</b> обновлены!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

