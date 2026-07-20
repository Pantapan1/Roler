from shared import *

@admin_router.message(Command("lore"))
async def read_lore(message: types.Message, command: CommandObject):
    if not command.args:
        topics = await db_execute("SELECT topic, category FROM lore", fetch=True)
        if not topics: return await message.answer("📚 Вики пуста.")
        return await message.answer("📚 <b>Статьи:</b>\n" + "\n".join([f"🔹 <code>{t[0]}</code> [{t[1]}]" for t in topics]) + "\n\n<i>Читай: /lore [название]</i>")
    
    res = await db_execute("SELECT description, category, views FROM lore WHERE topic = ?", (command.args.lower().strip(),), fetchone=True)
    if res:
        await db_execute("UPDATE lore SET views = views + 1 WHERE topic = ?", (command.args.lower().strip(),))
        await message.answer(f"📖 <b>{command.args}</b> [{res[1]}]\n👁 {res[2]+1}\n\n{res[0]}")
    else:
        await message.answer("❓ Статьи нет.")

