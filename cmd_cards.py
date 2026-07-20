from shared import *

@admin_router.message(Command("cards"))
async def list_card_packs(message: types.Message):
    packs = await db_execute("SELECT id, name, price, description FROM card_packs WHERE is_active = 1", fetch=True)
    if not packs:
        return await message.answer("🃏 Пакетов карт пока нет.")
    
    text = "🃏 <b>ПАКЕТЫ КАРТ:</b>\n\n"
    for row in packs:
        pack_id, name, price, desc = row
        cards = await db_execute("SELECT name, rarity, chance FROM cards WHERE pack_id = ?", (pack_id,), fetch=True)
        cards_text = "\n".join([f"  • {RARITY_ICONS.get(r[1], '')} {r[0]} ({r[2]}%)" for r in cards]) if cards else "  Пусто"
        text += f"🔹 <b>ID {pack_id}</b> — {name}\n   💰 {price} золота\n   {desc}\n   📦 Карты в пакете:\n{cards_text}\n\n"
    
    text += "<i>Открыть: /open_pack [ID]</i>"
    await message.answer(text)

