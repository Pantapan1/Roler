from shared import *

@market_router.message(Command("player_market"))
async def player_market_view(message: types.Message):
    items = await db_execute(
        "SELECT pm.id, pm.item_name, pm.price, pm.quantity, pm.rarity, u.character_name "
        "FROM player_market pm JOIN users u ON pm.seller_id = u.user_id WHERE pm.is_sold = 0",
        fetch=True
    )
    if not items:
        return await message.answer("💱 Рынок игроков пуст.")
    
    text = "💱 <b>РЫНОК ИГРОКОВ:</b>\n\n"
    for row in items:
        item_id, name, price, qty, rarity, seller = row
        text += f" [ID: <b>{item_id}</b>] {RARITY_ICONS.get(rarity, '⚪')} <b>{name}</b>\n"
        text += f"   💰 {price} золота | x{qty}\n"
        text += f"   🏪 Продавец: {seller}\n\n"
    
    text += "<i>Купить: /buy_market [ID]\nПродать: /sell [Предмет] [Цена]</i>"
    await message.answer(text)

