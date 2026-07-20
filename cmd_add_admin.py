from shared import *

@admin_router.message(Command("add_admin"))
async def add_admin_cmd(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        return await message.answer("⛔ Только главный админ может назначать админов.")
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /add_admin [ID пользователя]")
    uid = int(command.args)
    if uid == SUPER_ADMIN_ID: return await message.answer("Это главный админ.")
    await db_execute("INSERT OR IGNORE INTO admins (user_id, added_by) VALUES (?, ?)", (uid, SUPER_ADMIN_ID))
    invalidate_admin_cache(uid)
    await message.answer(f"✅ Пользователь ID {uid} назначен админом!")

