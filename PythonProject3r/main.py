import telebot
from telebot import types
import config
import time
from ban_system import ban_system, is_user_banned, ban_user_command, unban_user_command, ban_list_command

# Инициализация бота
bot = telebot.TeleBot(config.TOKEN)

# Словарь для хранения временных данных о заявках
pending_requests = {}
pending_media = {}


# Декоратор для проверки бана
def check_ban_decorator(func):
    def wrapper(message, *args, **kwargs):
        if is_user_banned(message.from_user.id):
            ban_info = ban_system.get_ban_info(message.from_user.id)

            if ban_info['permanent']:
                bot.send_message(
                    message.chat.id,
                    f"⛔ Вы забанены навсегда.\n"
                    f"Причина: {ban_info['reason'] or 'Не указана'}"
                )
            else:
                expires = ban_info['expires_at']
                remaining = expires - datetime.now()
                hours = remaining.seconds // 3600
                minutes = (remaining.seconds % 3600) // 60

                bot.send_message(
                    message.chat.id,
                    f"⛔ Вы забанены до {expires.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Осталось: {hours}ч {minutes}м\n"
                    f"Причина: {ban_info['reason'] or 'Не указана'}"
                )
            return
        return func(message, *args, **kwargs)

    return wrapper


# Функция для проверки прав администратора
def is_admin(message):
    """Проверяет, является ли пользователь администратором группы"""
    try:
        if message.chat.type not in ['group', 'supergroup']:
            return False

        admin_list = bot.get_chat_administrators(message.chat.id)
        admin_ids = [admin.user.id for admin in admin_list]
        return message.from_user.id in admin_ids
    except:
        return False


# Обработчик команды /start
@bot.message_handler(commands=['start'])
@check_ban_decorator
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🎮 Регистрация на турнире")
    btn2 = types.KeyboardButton("👥 Заявка на создание команды")
    markup.add(btn1, btn2)

    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в бота канала Game Zoom.\nвыберите что вам нужно\n\n"
        "Для обращения к администраторам канала и бота пишите в сообщения каналу",
        reply_markup=markup
    )


# Команда /ban для админов
@bot.message_handler(commands=['ban'])
def ban_command(message):
    if is_admin(message):
        ban_user_command(bot, message)
    else:
        bot.reply_to(message, "❌ У вас нет прав для использования этой команды")


# Команда /unban для админов
@bot.message_handler(commands=['unban'])
def unban_command(message):
    if is_admin(message):
        unban_user_command(bot, message)
    else:
        bot.reply_to(message, "❌ У вас нет прав для использования этой команды")


# Команда /banlist для админов
@bot.message_handler(commands=['banlist'])
def banlist_command(message):
    if is_admin(message):
        ban_list_command(bot, message)
    else:
        bot.reply_to(message, "❌ У вас нет прав для использования этой команды")


# Команда /myban для проверки своего бана
@bot.message_handler(commands=['myban'])
def myban_command(message):
    if is_user_banned(message.from_user.id):
        ban_info = ban_system.get_ban_info(message.from_user.id)
        if ban_info['permanent']:
            bot.reply_to(
                message,
                f"⛔ Вы забанены навсегда.\n"
                f"Причина: {ban_info['reason'] or 'Не указана'}"
            )
        else:
            expires = ban_info['expires_at']
            remaining = expires - datetime.now()
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60

            bot.reply_to(
                message,
                f"⛔ Вы забанены до {expires.strftime('%d.%m.%Y %H:%M')}\n"
                f"Осталось: {hours}ч {minutes}м\n"
                f"Причина: {ban_info['reason'] or 'Не указана'}"
            )
    else:
        bot.reply_to(message, "✅ Вы не забанены")


# Обработчик нажатия на кнопку "Регистрация на турнире"
@bot.message_handler(func=lambda message: message.text == "🎮 Регистрация на турнире")
@check_ban_decorator
def tournament_registration(message):
    msg = bot.send_message(
        message.chat.id,
        "📝 Заполните форму для регистрации на турнире.\n\n"
        "Форма:\n"
        "• Название команды\n"
        "• Участники:\n\n"
        "• Дата:\n\n"
        "Внимание! если среди участников есть азабаненые игроки то команда не будет участвовать. доп. информацию смотрите в посте об объявлении турнира"
    )
    bot.register_next_step_handler(msg, process_content, 'tournament')


# Обработчик нажатия на кнопку "Заявка на создание команды"
@bot.message_handler(func=lambda message: message.text == "👥 Заявка на создание команды")
@check_ban_decorator
def team_creation(message):
    msg = bot.send_message(
        message.chat.id,
        "📝 Заполните форму для создания команды\n\n"
        "Форма\n"
        "• Название:\n"
        "• Игра: (например CS2)\n"
        "• Капитан:\n"
        "• Игроки(ники в игре):\n"
        "• телеграмм канал (по желанию):\n\n"
        "Внимание! можно внести сколько угодно игроков в список участников (главное чтобы это были реальные участники). так же можно добавить логотип своей команды по желанию"
    )
    bot.register_next_step_handler(msg, process_content, 'team')


# Функция для отправки медиа в группу
def send_media_to_group_with_retry(group_id, media_type, file_id, caption, max_retries=3):
    for attempt in range(max_retries):
        try:
            if media_type == 'photo':
                return bot.send_photo(group_id, file_id, caption=caption)
            elif media_type == 'video':
                return bot.send_video(group_id, file_id, caption=caption)
            elif media_type == 'document':
                return bot.send_document(group_id, file_id, caption=caption)
            elif media_type == 'animation':
                return bot.send_animation(group_id, file_id, caption=caption)
            else:
                return bot.send_message(group_id, caption)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Попытка {attempt + 1} не удалась, повтор через 2 секунды...")
                time.sleep(2)
            else:
                print(f"Не удалось отправить медиа в группу {group_id} после {max_retries} попыток")
                raise e


# Функция для отправки текста в группу
def send_to_group_with_retry(group_id, text, max_retries=3):
    for attempt in range(max_retries):
        try:
            return bot.send_message(group_id, text)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Попытка {attempt + 1} не удалась, повтор через 2 секунды...")
                time.sleep(2)
            else:
                print(f"Не удалось отправить сообщение в группу {group_id} после {max_retries} попыток")
                raise e


# Обработка контента от пользователя
def process_content(message, request_type):
    try:
        username = message.from_user.username
        username_text = f"@{username}" if username else f"ID: {message.from_user.id}"

        content_type = message.content_type
        file_id = None
        caption = ""

        if hasattr(message, 'caption') and message.caption:
            caption = message.caption
        elif content_type == 'text':
            caption = message.text

        header = f"{'🎮 НОВАЯ ЗАЯВКА НА ТУРНИР' if request_type == 'tournament' else '👥 НОВАЯ ЗАЯВКА НА СОЗДАНИЕ КОМАНДЫ'}\n\n"
        user_info = f"От: {message.from_user.full_name}\nUsername: {username_text}\nUser ID: {message.from_user.id}\n\n"

        if content_type == 'text':
            admin_message = header + user_info + f"Текст заявки:\n{message.text}"
            sent_message = send_to_group_with_retry(
                config.TOURNAMENT_GROUP_ID if request_type == 'tournament' else config.TEAM_GROUP_ID,
                admin_message
            )
        else:
            media_types = {
                'photo': ('photo', '📸 Фото'),
                'video': ('video', '🎥 Видео'),
                'animation': ('animation', '🎬 GIF'),
                'document': ('document', '📄 Документ')
            }

            if content_type in media_types:
                media_type, emoji = media_types[content_type]
                if content_type == 'photo':
                    file_id = message.photo[-1].file_id
                else:
                    file_id = getattr(message, content_type).file_id

                admin_message = header + user_info + f"{emoji} с подписью:\n{caption if caption else 'Без подписи'}"

                sent_message = send_media_to_group_with_retry(
                    config.TOURNAMENT_GROUP_ID if request_type == 'tournament' else config.TEAM_GROUP_ID,
                    media_type,
                    file_id,
                    admin_message
                )

                pending_media[sent_message.message_id] = {
                    'media_type': media_type,
                    'file_id': file_id,
                    'caption': admin_message
                }

        # Добавляем кнопки для админов
        markup = types.InlineKeyboardMarkup()
        btn_accept = types.InlineKeyboardButton(
            "✅ | Принять",
            callback_data=f"accept_{request_type}_{sent_message.message_id}"
        )
        btn_reject = types.InlineKeyboardButton(
            "❌ | Отклонить",
            callback_data=f"reject_{request_type}_{sent_message.message_id}"
        )
        markup.add(btn_accept, btn_reject)

        # Обновляем сообщение с кнопками
        try:
            if content_type == 'text':
                bot.edit_message_text(
                    chat_id=config.TOURNAMENT_GROUP_ID if request_type == 'tournament' else config.TEAM_GROUP_ID,
                    message_id=sent_message.message_id,
                    text=admin_message + "\n\n👇 Действия админа:",
                    reply_markup=markup
                )
            else:
                bot.edit_message_caption(
                    chat_id=config.TOURNAMENT_GROUP_ID if request_type == 'tournament' else config.TEAM_GROUP_ID,
                    message_id=sent_message.message_id,
                    caption=admin_message + "\n\n👇 Действия админа:",
                    reply_markup=markup
                )
        except Exception as e:
            print(f"Не удалось добавить кнопки к сообщению: {e}")

        # Сохраняем информацию о заявке
        pending_requests[sent_message.message_id] = {
            'chat_id': message.chat.id,
            'type': request_type,
            'username': username_text,
            'user_name': message.from_user.full_name,
            'content_type': content_type,
            'message_id': sent_message.message_id
        }

        bot.send_message(
            message.chat.id,
            "✅ Ваша заявка отправлена администраторам! Ожидайте решения."
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при отправке заявки. Пожалуйста, попробуйте позже или свяжитесь с администратором."
        )
        print(f"Ошибка в process_content: {e}")


# Обработчик для всех типов контента
@bot.message_handler(content_types=['text', 'photo', 'video', 'animation', 'document'])
@check_ban_decorator
def handle_all_content(message):
    if message.text not in ["🎮 Регистрация на турнире", "👥 Заявка на создание команды"]:
        bot.send_message(
            message.chat.id,
            "Пожалуйста, используйте кнопки ниже для создания заявки:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("🎮 Регистрация на турнире"),
                types.KeyboardButton("👥 Заявка на создание команды")
            )
        )


# Обработчик нажатий на инлайн кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        data_parts = call.data.split('_')
        action = data_parts[0]
        request_type = data_parts[1]
        message_id = int(data_parts[2])

        if message_id not in pending_requests:
            bot.answer_callback_query(call.id, "❌ Заявка уже обработана или не найдена!")
            return

        request_data = pending_requests[message_id]
        user_chat_id = request_data['chat_id']

        if action == 'accept':
            if request_type == 'tournament':
                user_message = "Админ принял вашу заявку. Ваша команда участвует на турнире!"
            else:
                user_message = ("Админ принял вашу заявку. Ваша команда будет добавлена в течении ~5 - 10 минут "
                                "(если админ так и не добавил вашу команду просьба написать в сообщения каналу)")

            try:
                bot.send_message(user_chat_id, f"✅ {user_message}")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю: {e}")

            admin_feedback = "✅ Заявка принята!"
        else:
            try:
                bot.send_message(user_chat_id, "❌ Ваша заявка была отклонена администратором.")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю: {e}")

            admin_feedback = "❌ Заявка отклонена!"

        group_id = config.TOURNAMENT_GROUP_ID if request_type == 'tournament' else config.TEAM_GROUP_ID

        try:
            if message_id in pending_media:
                bot.edit_message_caption(
                    chat_id=group_id,
                    message_id=message_id,
                    caption=call.message.caption + f"\n\nСтатус: {admin_feedback}",
                    reply_markup=None
                )
            else:
                bot.edit_message_text(
                    chat_id=group_id,
                    message_id=message_id,
                    text=call.message.text + f"\n\nСтатус: {admin_feedback}",
                    reply_markup=None
                )
        except Exception as e:
            print(f"Не удалось обновить сообщение в группе: {e}")
            bot.send_message(
                group_id,
                f"Заявка #{message_id} обработана. Статус: {admin_feedback}"
            )

        del pending_requests[message_id]
        if message_id in pending_media:
            del pending_media[message_id]

        bot.answer_callback_query(call.id, admin_feedback)

    except Exception as e:
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")
        print(f"Ошибка в handle_callback: {e}")


# Функция для проверки групп
def check_groups():
    print("🔍 Проверка групп...")

    try:
        bot_info = bot.get_me()
        print(f"✅ Бот @{bot_info.username} успешно запущен")
    except Exception as e:
        print(f"❌ Ошибка при получении информации о боте: {e}")
        return False

    try:
        test_msg = bot.send_message(config.TOURNAMENT_GROUP_ID, "🔄 Бот запущен и проверяет доступ к группе...")
        bot.delete_message(config.TOURNAMENT_GROUP_ID, test_msg.message_id)
        print(f"✅ Турнирная группа (ID: {config.TOURNAMENT_GROUP_ID}) доступна")
    except Exception as e:
        print(f"❌ Ошибка доступа к турнирной группе (ID: {config.TOURNAMENT_GROUP_ID})")
        print(f"   Причина: {e}")

    try:
        test_msg = bot.send_message(config.TEAM_GROUP_ID, "🔄 Бот запущен и проверяет доступ к группе...")
        bot.delete_message(config.TEAM_GROUP_ID, test_msg.message_id)
        print(f"✅ Группа для команд (ID: {config.TEAM_GROUP_ID}) доступна")
    except Exception as e:
        print(f"❌ Ошибка доступа к группе для команд (ID: {config.TEAM_GROUP_ID})")
        print(f"   Причина: {e}")

    return True


# Запуск бота
if __name__ == '__main__':
    print("🚀 Запуск бота...")

    # Проверяем доступность групп
    check_groups()

    # Очищаем истекшие баны при запуске
    expired = ban_system.clear_expired_bans()
    if expired > 0:
        print(f"🧹 Очищено {expired} истекших банов")

    print("\n🔄 Бот запущен и ожидает сообщения...")
    print("Нажмите Ctrl+C для остановки\n")

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")