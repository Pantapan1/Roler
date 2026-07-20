import asyncio
from shared import bot, dp, init_db, set_bot_commands, PIL_AVAILABLE, SUPER_ADMIN_ID

# Импортируем все файлы с командами, чтобы зарегистрировать обработчики
import cmd_cancel  # noqa: F401
import cmd_help  # noqa: F401
import cmd_combat_end  # noqa: F401
import cmd_start  # noqa: F401
import cmd_register_name  # noqa: F401
import cmd_register_bio  # noqa: F401
import cmd_join  # noqa: F401
import cmd_spectate  # noqa: F401
import cmd_me  # noqa: F401
import cmd_me_text  # noqa: F401
import cmd_create_lootbox  # noqa: F401
import cmd_create_lootbox_name  # noqa: F401
import cmd_create_lootbox_price  # noqa: F401
import cmd_create_lootbox_items  # noqa: F401
import cmd_add_loot  # noqa: F401
import cmd_lootboxes  # noqa: F401
import cmd_open_loot  # noqa: F401
import cmd_create_card_pack  # noqa: F401
import cmd_create_card_pack_name  # noqa: F401
import cmd_create_card_pack_price  # noqa: F401
import cmd_create_card_pack_cards  # noqa: F401
import cmd_add_card  # noqa: F401
import cmd_cards  # noqa: F401
import cmd_open_pack  # noqa: F401
import cmd_my_cards  # noqa: F401
import cmd_fav_card  # noqa: F401
import cmd_create_pet  # noqa: F401
import cmd_create_pet_name  # noqa: F401
import cmd_create_pet_desc  # noqa: F401
import cmd_create_pet_rarity  # noqa: F401
import cmd_create_pet_stats  # noqa: F401
import cmd_add_pet_stat  # noqa: F401
import cmd_pets  # noqa: F401
import cmd_tame_pet  # noqa: F401
import cmd_my_pets  # noqa: F401
import cmd_equip_pet  # noqa: F401
import cmd_feed_pet  # noqa: F401
import cmd_pet_items  # noqa: F401
import cmd_player_market  # noqa: F401
import cmd_sell  # noqa: F401
import cmd_buy_market  # noqa: F401
import cmd_my_sales  # noqa: F401
import cmd_cancel_sale  # noqa: F401
import cmd_add_admin  # noqa: F401
import cmd_users  # noqa: F401
import cmd_set_stats  # noqa: F401
import cmd_roll  # noqa: F401
import cmd_use  # noqa: F401
import cmd_equip  # noqa: F401
import cmd_trade  # noqa: F401
import cmd_spawn  # noqa: F401
import cmd_combat_start  # noqa: F401
import cmd_next_turn  # noqa: F401
import cmd_panel  # noqa: F401
import cmd_select_entity_action  # noqa: F401
import cmd_gm_action_prompt  # noqa: F401
import cmd_execute_gm_action  # noqa: F401
import cmd_add_location  # noqa: F401
import cmd_move  # noqa: F401
import cmd_lore  # noqa: F401
import cmd_location  # noqa: F401
import cmd_locations  # noqa: F401
import cmd_quest  # noqa: F401
import cmd_set_quest  # noqa: F401
import cmd_w  # noqa: F401
import cmd_active  # noqa: F401
import cmd_find  # noqa: F401
import cmd_add_market  # noqa: F401
import cmd_market  # noqa: F401
import cmd_buy  # noqa: F401
import cmd_time  # noqa: F401
import cmd_env  # noqa: F401
import cmd_event  # noqa: F401
import cmd_npc  # noqa: F401
import cmd_open_session  # noqa: F401
import cmd_archive  # noqa: F401
import cmd_broadcast  # noqa: F401
import cmd_broadcast_send  # noqa: F401
import cmd_remove_admin  # noqa: F401
import cmd_admins  # noqa: F401
import cmd_dashboard  # noqa: F401
import cmd_user_stats  # noqa: F401
import cmd_room_create  # noqa: F401
import cmd_room_create_finish  # noqa: F401
import cmd_room_list  # noqa: F401
import cmd_room_join  # noqa: F401
import cmd_room_leave  # noqa: F401
import cmd_rp_chat_router  # noqa: F401
import cmd_on_error  # noqa: F401

async def main():
    init_db()
    await set_bot_commands(bot)
    print("🚀 Бот запущен!")
    print(f"👑 Админ: {SUPER_ADMIN_ID}")
    print(f"🎨 Pillow: {'✅' if PIL_AVAILABLE else '❌'}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())