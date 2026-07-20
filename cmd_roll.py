from shared import *

@admin_router.message(Command("roll"))
@player_router.message(Command("roll"))
async def roll_dice_cmd(message: types.Message, command: CommandObject):
    user_id, chat_id = message.from_user.id, message.chat.id
    room_id = await get_user_room(user_id)
    char_name = await get_character(user_id) or "Неизвестный"
    bonus, stat_name, dice_str = 0, "", "1d20"
    
    if command.args:
        arg = command.args.lower().strip()
        if arg in ['str', 'сила', 'agi', 'ловкость', 'int', 'интеллект']:
            stats = await db_execute("SELECT strength, agility, intelligence FROM users WHERE user_id = ?", (user_id,), fetchone=True)
            if stats:
                if 'str' in arg or 'сила' in arg: bonus, stat_name = stats[0], "(Сила)"
                elif 'agi' in arg or 'ловк' in arg: bonus, stat_name = stats[1], "(Ловкость)"
                elif 'int' in arg or 'интел' in arg: bonus, stat_name = stats[2], "(Интеллект)"
        else: dice_str = arg
    
    rolls, mod, total = roll_dice(dice_str)
    final_total = total + bonus
    roll_text = f"<b>{rolls[0]}</b>" if len(rolls) == 1 else "[" + "+".join(str(r) for r in rolls) + "]"
    mod_text = f" {'+' if mod > 0 else ''}{mod}" if mod != 0 else ""
    bonus_text = f" + {bonus} {stat_name}" if bonus != 0 else ""
    
    await broadcast_to_session(chat_id, f"🎲 <b>{char_name}</b> бросает {dice_str}{mod_text}{bonus_text}:\n{roll_text} = <b>{final_total}</b>", room_id)

