from shared import *

@admin_router.callback_query(F.data.startswith("gm_sel_"))
async def select_entity_action(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    parts = callback.data.split("_")
    await state.update_data(target_id=int(parts[3]), target_type=parts[2])
    kb = [[InlineKeyboardButton(text="⚔️ Урон", callback_data="gm_act_damage"), InlineKeyboardButton(text="💊 Хил", callback_data="gm_act_heal")]]
    if parts[2] == 'monster': kb.append([InlineKeyboardButton(text="💀 Убить", callback_data="gm_act_kill")])
    await callback.message.edit_text("Действие:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

