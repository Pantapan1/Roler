from shared import *

@admin_router.message(Command("help"))
@player_router.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "📜 <b>СПРАВОЧНИК ИГРОКА</b>\n\n"
        "🔹 /create — Создать персонажа\n"
        "🔹 /join | /spectate — Войти как Игрок / Зритель\n"
        "🔹 /me — Профиль (картинка)\n"
        "🔹 /me_text — Профиль (текст)\n"
        "🔹 <code>/use [Название]</code> — Использовать предмет\n"
        "🔹 <code>/equip [Название]</code> — Надеть/снять предмет\n"
        "🔹 <code>/trade [Имя] [Предмет]</code> — Передать предмет\n"
        "🔹 /market — Рынок ГМа (купить: <code>/buy [ID]</code>)\n"
        "🔹 /player_market — Рынок игроков\n"
        "🔹 <code>/sell [Предмет] [Цена]</code> — Продать на рынке\n"
        "🔹 /buy_market [ID] — Купить с рынка игроков\n"
        "🔹 /lore — Вики по миру\n"
        " /quest — Текущее задание\n"
        "🔹 /location — Текущая локация\n"
        "🔹 <code>/w [Имя] [Текст]</code> — Шепот\n"
        "🔹 <code>/roll [XdY+Z]</code> — Бросок кубика\n\n"
        
        "🏠 <b>КОМНАТЫ:</b>\n"
        "🔹 /room_create — Создать комнату\n"
        "🔹 /room_list — Список комнат\n"
        "🔹 <code>/room_join [ID]</code> — Войти\n"
        "🔹 /room_leave — Выйти\n\n"
        
        " <b>СУНДУКИ И КАРТЫ:</b>\n"
        " /lootboxes — Список сундуков\n"
        "🔹 <code>/open_loot [ID]</code> — Открыть сундук\n"
        "🔹 /cards — Пакеты карт\n"
        "🔹 <code>/open_pack [ID]</code> — Открыть пакет\n"
        "🔹 /my_cards — Моя коллекция\n\n"
        
        " <b>ПИТОМЦЫ:</b>\n"
        "🔹 /pets — Доступные питомцы\n"
        "🔹 /my_pets — Мои питомцы\n"
        "🔹 <code>/equip_pet [ID]</code> — Приручить питомца\n"
        "🔹 <code>/feed_pet [ID] [Еда]</code> — Покормить\n\n"
        
        "👥 <b>ПОЛЬЗОВАТЕЛИ:</b>\n"
        "🔹 /users — Все пользователи\n"
        "🔹 /active — Кто в сессии\n"
        "🔹 <code>/find [Имя/ID]</code> — Найти игрока\n\n"
        
        "💡 <b>ОТЫГРЫШ:</b>\n"
        "<code>*действия*</code> → <i>курсив</i>\n"
        "<code>(мысли)</code> → 💭 <i>мысли</i>\n"
        "<code>\"речь\"</code> → 🗣 <b>речь</b>\n"
    )
    
    if await is_admin(message.from_user.id):
        text += (
            "\n🛠 <b>КОМАНДЫ ГМа</b>\n\n"
            "🔸 /open_session | /archive — Сессия\n"
            "🔸 /panel — Панель управления\n"
            " /broadcast — Рассылка\n"
            "🔸 /spawn [ХП] [Имя] — Монстр\n"
            "🔸 <b>БОЙ:</b> /combat_start, /next_turn, /combat_end\n"
            "🔸 <b>РЫНОК:</b> <code>/add_market [Кол-во] [Цена] [Название] - [Описание] [Редкость]</code>\n"
            "🔸 <b>СУНДУКИ:</b> /create_lootbox, <code>/add_loot [ID сундука] [Предмет] [Редкость] [Шанс%]</code>\n"
            "🔸 <b>КАРТЫ:</b> /create_card_pack, <code>/add_card [ID пакета] [Название] [Редкость] [Шанс%]</code>\n"
            "🔸 <b>ПИТОМЦЫ:</b> /create_pet, <code>/add_pet_stat [Название] [STR] [AGI] [INT]</code>\n"
            " <b>СТАТЫ:</b> <code>/set_stats [ID] [STR] [AGI] [INT]</code>\n"
            "🔸 <b>ЛОКАЦИИ:</b> /add_location, /locations, <code>/move [Название]</code>\n"
            "🔸 <b>ВРЕМЯ:</b> <code>/time [утро/день/вечер/ночь]</code>\n"
            "🔸 <b>АДМИНЫ:</b> <code>/add_admin [ID]</code>, <code>/remove_admin [ID]</code>, /admins\n"
            "🔸 <b>ПОЛЬЗОВАТЕЛИ:</b> /dashboard, <code>/user_stats [ID]</code>\n"
            "🔸 <code>/set_quest</code>, <code>/env</code>, <code>/event</code>, <code>/npc</code>\n"
        )
    await message.answer(text)

