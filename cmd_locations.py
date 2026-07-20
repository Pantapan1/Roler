from shared import *

@admin_router.message(Command("locations"))
async def list_locations(message: types.Message):
    if not await is_admin(message.from_user.id): return
    locs = await db_execute("SELECT name FROM locations", fetch=True)
    if not locs: return await message.answer("🗺 Локаций нет. Добавь через /add_location")
    await message.answer("🗺 <b>Локации:</b>\n" + "\n".join(f"🔹 {l[0]}" for l in locs))

