from shared import *

@admin_router.callback_query(F.data.startswith("gm_act_"))
async def gm_action_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    action = callback.data.split("_")[2]
    if action == "kill":
        data = await state.get_data()
        await db_execute("DELETE FROM session_monsters WHERE id = ?", (data['target_id'],))
        s = get_session(callback.message.chat.id, await get_user_room(callback.from_user.id))
        s.combat_queue = [q for q in s.combat_queue if not (q['type'] == 'monster' and q['id'] == data['target_id'])]
        await callback.message.edit_text("💀 Монстр уничтожен!")
        return
    await state.update_data(action_type=action)
    await state.set_state(GMAction.waiting_for_value)
    await callback.message.edit_text("Введи число (урон/хил):")

