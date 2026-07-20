from shared import *

@admin_router.message(Command("admins"))
async def list_admins(message: types.Message):
    if not await is_admin(message.from_user.id): return
    admins = await db_execute("SELECT user_id FROM admins", fetch=True)
    text = f"👑 Главный админ: <code>{SUPER_ADMIN_ID}</code>\n"
    text += "\n".join(f"🔸 <code>{a[0]}</code>" for a in admins) if admins else "Других админов нет."
    await message.answer(text)

