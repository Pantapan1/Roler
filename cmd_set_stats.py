from shared import *

@admin_router.message(Command("set_stats"))
async def set_player_stats(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    args = command.args.split() if command.args else []
    if len(args) != 4: return await message.answer("Формат: /set_stats [ID] [STR] [AGI] [INT]")
    try:
        await db_execute("UPDATE users SET strength=?, agility=?, intelligence=? WHERE user_id=?", (int(args[1]), int(args[2]), int(args[3]), int(args[0])))
        await message.answer(f"✅ Статы обновлены для ID {args[0]}.")
    except: await message.answer("Ошибка ввода.")

