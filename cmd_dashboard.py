from shared import *

@admin_router.message(Command("dashboard"))
async def dashboard(message: types.Message):
    if not await is_admin(message.from_user.id): return
    total_users = await db_execute("SELECT COUNT(*) FROM users", fetchone=True)
    total_players = await db_execute("SELECT COUNT(*) FROM session_players WHERE status='player'", fetchone=True)
    total_rooms = await db_execute("SELECT COUNT(*) FROM rooms WHERE is_active=1", fetchone=True)
    total_monsters = await db_execute("SELECT COUNT(*) FROM session_monsters", fetchone=True)
    text = (
        "📊 <b>ДАШБОРД</b>\n\n"
        f"👥 Персонажей: {total_users[0]}\n"
        f"⚔️ В сессиях: {total_players[0]}\n"
        f"🏠 Активных комнат: {total_rooms[0]}\n"
        f"🐉 Монстров в игре: {total_monsters[0]}\n"
        f"🎨 Pillow: {'✅' if PIL_AVAILABLE else '❌'}"
    )
    await message.answer(text)

