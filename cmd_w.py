from shared import *

@admin_router.message(Command("w"))
@player_router.message(Command("w"))
async def whisper_cmd(message: types.Message, command: CommandObject):
    if not command.args: return await message.answer("Формат: /w [Имя] [Текст]")
    args = command.args.split(maxsplit=1)
    if len(args) < 2: return await message.answer("Формат: /w [Имя] [Текст]")
    target_name, text = args
    user_id = message.from_user.id
    sender_name = await get_character(user_id) or "Неизвестный"
    target = await db_execute("SELECT user_id FROM users WHERE character_name = ?", (target_name,), fetchone=True)
    if not target: return await message.answer("❌ Игрок не найден.")
    if target[0] == user_id: return await message.answer("❌ Нельзя шептать самому себе.")
    formatted = format_rp_text(text)
    try:
        await bot.send_message(target[0], f"🤫 <i>Шёпот от <b>{sender_name}</b>:</i>\n{formatted}")
    except Exception:
        return await message.answer("❌ Не удалось отправить (игрок не запускал бота).")
    await message.answer(f"🤫 Шёпот отправлен игроку <b>{target_name}</b>.")

