from shared import *

@admin_router.message(Command("me_text"))
@player_router.message(Command("me_text"))
async def check_stats_text(message: types.Message):
    user_id = message.from_user.id
    user_data = await db_execute(
        "SELECT character_name, bio, hp, max_hp, xp, level, gold, strength, agility, intelligence, location FROM users WHERE user_id = ?",
        (user_id,), fetchone=True
    )
    if not user_data:
        return await message.answer("Сначала создай персонажа через /create")
    
    name, bio, hp, max_hp, xp, level, gold, str_s, agi_s, int_s, location = user_data
    items = await db_execute("SELECT item_name, quantity, is_equipped, rarity FROM inventory WHERE user_id = ?", (user_id,), fetch=True)
    effects = await db_execute("SELECT effect_name, duration FROM effects WHERE user_id = ?", (user_id,), fetch=True)
    
    inv_list = []
    for row in items:
        prefix = "⚔️ [НАДЕТО] " if row[2] else "🔹 "
        r_icon = RARITY_ICONS.get(row[3], '⚪')
        inv_list.append(f"{prefix}{r_icon} {row[0]} (x{row[1]})")
    inv_text = "\n".join(inv_list) if inv_list else "Пусто"
    
    eff_list = [f"• {row[0]} ({row[1]} ходов)" for row in effects]
    eff_text = "\n".join(eff_list) if eff_list else "Нет"
    
    hp_bar = "█" * max(0, min(10, int(hp / max_hp * 10))) + "░" * max(0, 10 - int(hp / max_hp * 10))
    
    text = (
        f"━━━━━━━━━━━━ ⚔️ ━━━━━━━━━━━━\n"
        f"👤 <b>{name}</b> (Ур. {level})\n"
        f" {bio}\n\n"
        f"❤️ <b>HP:</b> {hp}/{max_hp} [{hp_bar}]\n"
        f"✨ <b>XP:</b> {xp} | 🪙 <b>Золото:</b> {gold}\n\n"
        f"🧬 <b>Характеристики:</b>\n"
        f"💪 Сила: {str_s} | 🏃 Ловкость: {agi_s} |  Интеллект: {int_s}\n\n"
        f"📍 <b>Локация:</b> {location}\n\n"
        f"🎒 <b>Инвентарь:</b>\n{inv_text}\n\n"
        f"🩸 <b>Эффекты:</b>\n{eff_text}\n"
        f"━━━━━━━━━━━━ ⚔️ ━━━━━━━━━━━"
    )
    await message.answer(text)

