from shared import *

@admin_router.message(Command("add_location"))
async def add_location(message: types.Message, command: CommandObject, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    if not command.args: return await message.answer("Формат: /add_location [Название] - [Описание]")
    name, desc = command.args.split("-", 1)
    await db_execute("INSERT OR REPLACE INTO locations (name, description) VALUES (?, ?)", (name.strip(), desc.strip()))
    await message.answer(f"✅ Локация <b>{name.strip()}</b> добавлена.")

