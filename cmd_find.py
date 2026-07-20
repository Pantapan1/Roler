from shared import *

@admin_router.message(Command("find"))
@player_router.message(Command("find"))
async def find_player(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /find [Имя или ID]")
    query = command.args.strip()
    if query.isdigit():
        res = await db_execute("SELECT user_id, character_name, level, location FROM users WHERE user_id = ?", (int(query),), fetchone=True)
    else:
        res = await db_execute("SELECT user_id, character_name, level, location FROM users WHERE character_name = ?", (query,), fetchone=True)
    if not res: return await message.answer("❌ Не найден.")
    await message.answer(f"👤 <b>{res[1]}</b> (Ур. {res[2]})\n🆔 <code>{res[0]}</code>\n📍 {res[3]}")

