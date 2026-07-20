from shared import *

@market_router.message(Command("market"))
async def gm_market_view(message: types.Message):
    items = await db_execute("SELECT id, item_name, price, description, quantity, rarity FROM market WHERE quantity > 0", fetch=True)
    if not items: return await message.answer("🛒 Рынок ГМа пуст.")
    text = "🛒 <b>РЫНОК МАСТЕРА:</b>\n\n"
    for row in items:
        iid, name, price, desc, qty, rarity = row
        text += f"[ID: <b>{iid}</b>] {RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b>\n   💰 {price} золота | В наличии: {qty}\n"
        if desc:
            text += f"   <i>{desc}</i>\n"
        text += "\n"
    text += "<i>Купить: /buy [ID]</i>"
    await message.answer(text)

