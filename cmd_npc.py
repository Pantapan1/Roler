from shared import *

@admin_router.message(Command("npc"))
async def set_active_npc(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id): return
    chat_id, user_id = message.chat.id, message.from_user.id
    room_id = await get_user_room(user_id)
    s = get_session(chat_id, room_id)
    if not command.args:
        s.active_npc = None
        return await message.answer("🎭 Режим NPC выключен.")
    s.active_npc = command.args.strip()
    await message.answer(f"🎭 Теперь ты говоришь как <b>{s.active_npc}</b> в сессии. Выключить: /npc")

