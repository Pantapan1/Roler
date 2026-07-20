from shared import *

@admin_router.message(Command("lootboxes"))
async def list_lootboxes(message: types.Message):
    boxes = await db_execute("SELECT id, name, price, description FROM loot_boxes WHERE is_active = 1", fetch=True)
    if not boxes:
        return await message.answer("🎁 Сундуков пока нет.")
    
    text = "🎁 <b>ДОСТУПНЫЕ СУНДУКИ:</b>\n\n"
    for row in boxes:
        box_id, name, price, desc = row
        items = await db_execute("SELECT item_name, rarity, chance FROM loot_box_items WHERE box_id = ?", (box_id,), fetch=True)
        items_text = "\n".join([f"  • {RARITY_ICONS.get(r[1], '⚪')} {r[0]} ({r[2]}%)" for r in items]) if items else "  Пусто"
        text += f"🔹 <b>ID {box_id}</b> — {name}\n   💰 {price} золота\n   {desc}\n   📦 Возможный лут:\n{items_text}\n\n"
    
    text += "<i>Открыть: /open_loot [ID]</i>"
    await message.answer(text)

