from shared import *

@admin_router.message(Command("remove_admin"))
async def remove_admin_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        return await message.answer("⛔ Только главный админ может снимать админов.")
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /remove_admin [ID пользователя]")
    uid = int(command.args)
    await db_execute("DELETE FROM admins WHERE user_id = ?", (uid,))
    invalidate_admin_cache(uid)
    await message.answer(f"✅ Пользователь ID {uid} больше не админ.")

