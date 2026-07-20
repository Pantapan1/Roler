from shared import *

@admin_router.message(Command("user_stats"))
async def user_stats(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    if not command.args or not command.args.isdigit():
        return await message.answer("Формат: /user_stats [ID]")
    uid = int(command.args)
    u = await db_execute(
        "SELECT character_name, hp, max_hp, xp, level, gold, strength, agility, intelligence, location, messages_count, created_at, last_active FROM users WHERE user_id = ?",
        (uid,), fetchone=True
    )
    if not u: return await message.answer("❌ Пользователь не найден.")
    name, hp, max_hp, xp, level, gold, s_, a_, i_, loc, msgs, created, active = u
    text = (
        f"📋 <b>{name}</b> (ID: <code>{uid}</code>)\n\n"
        f"❤️ HP: {hp}/{max_hp} | Ур. {level} | ✨ XP: {xp}\n"
        f"💪 {s_} 🏃 {a_} 🧠 {i_} | 🪙 {gold}\n"
        f"📍 {loc}\n"
        f"💬 Сообщений: {msgs}\n"
        f"📅 Создан: {created}\n"
        f"🕐 Активен: {active}\n"
        f"🛠 Админ: {'Да' if await is_admin(uid) else 'Нет'}"
    )
    await message.answer(text)

