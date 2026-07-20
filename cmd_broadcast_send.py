from shared import *

@admin_router.message(GMBroadcast.waiting_message, F.text)
async def broadcast_send(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    users = await db_execute("SELECT user_id FROM users", fetch=True)
    sent = 0
    for row in users:
        try:
            await bot.send_message(row[0], f"📢 <b>ОБЪЯВЛЕНИЕ МАСТЕРА:</b>\n\n{message.text}")
            sent += 1
            await asyncio.sleep(0.03)
        except Exception:
            pass
    await state.clear()
    await message.answer(f"✅ Рассылка отправлена: {sent}/{len(users)}")

