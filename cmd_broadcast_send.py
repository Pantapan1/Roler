from shared import *

@admin_router.message(GMBroadcast.waiting_message, F.text | F.photo)
async def broadcast_send(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    text = message.text or message.caption or ""
    caption = f"📢 <b>ОБЪЯВЛЕНИЕ МАСТЕРА:</b>\n\n{text}" if text else "📢 <b>ОБЪЯВЛЕНИЕ МАСТЕРА:</b>"
    users = await db_execute("SELECT user_id FROM users", fetch=True)
    sent = 0
    for row in users:
        try:
            if message.photo:
                await bot.send_photo(row[0], message.photo[-1].file_id, caption=caption)
            else:
                await bot.send_message(row[0], caption)
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Рассылка отправлена: {sent}/{len(users)}")

