from shared import *

@market_router.message(Command("my_sales"))
async def my_sales(message: types.Message):
    user_id = message.from_user.id
    sales = await db_execute(
        "SELECT id, item_name, price, quantity, is_sold FROM player_market WHERE seller_id = ?",
        (user_id,), fetch=True
    )
    if not sales:
        return await message.answer(" У тебя нет лотов на рынке.")
    
    text = "🏪 <b>ТВОИ ЛОТЫ:</b>\n\n"
    for row in sales:
        lot_id, name, price, qty, sold = row
        status = "✅ Продано" if sold else "🟢 Активно"
        text += f"[ID: {lot_id}] <b>{name}</b> x{qty} — {price} золота — {status}\n"
    
    text += "\n<i>Снять: /cancel_sale [ID]</i>"
    await message.answer(text)

