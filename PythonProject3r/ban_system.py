import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time


class BanSystem:
    def __init__(self, ban_file='bans.json'):
        """
        Инициализация системы банов
        :param ban_file: путь к файлу для хранения банов
        """
        self.ban_file = ban_file
        self.bans = self._load_bans()

    def _load_bans(self) -> Dict:
        """Загружает список банов из файла"""
        if os.path.exists(self.ban_file):
            try:
                with open(self.ban_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем строки обратно в datetime для истечения срока
                    for user_id, ban_info in data.items():
                        if 'expires_at' in ban_info and ban_info['expires_at']:
                            ban_info['expires_at'] = datetime.fromisoformat(ban_info['expires_at'])
                    return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка при загрузке банов: {e}")
                return {}
        return {}

    def _save_bans(self):
        """Сохраняет список банов в файл"""
        try:
            # Конвертируем datetime в строки для JSON
            bans_to_save = {}
            for user_id, ban_info in self.bans.items():
                bans_to_save[user_id] = ban_info.copy()
                if 'expires_at' in ban_info and ban_info['expires_at']:
                    bans_to_save[user_id]['expires_at'] = ban_info['expires_at'].isoformat()

            with open(self.ban_file, 'w', encoding='utf-8') as f:
                json.dump(bans_to_save, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"Ошибка при сохранении банов: {e}")

    def ban_user(self, user_id: int, admin_id: int, reason: str = "", duration: Optional[int] = None) -> bool:
        """
        Банит пользователя
        :param user_id: ID пользователя
        :param admin_id: ID администратора
        :param reason: причина бана
        :param duration: длительность бана в часах (None = навсегда)
        :return: True если успешно, False если уже забанен
        """
        user_id_str = str(user_id)

        # Проверяем, не забанен ли уже пользователь
        if self.is_banned(user_id):
            return False

        ban_info = {
            'user_id': user_id,
            'admin_id': admin_id,
            'reason': reason,
            'banned_at': datetime.now().isoformat(),
            'expires_at': datetime.now() + timedelta(hours=duration) if duration else None,
            'permanent': duration is None
        }

        self.bans[user_id_str] = ban_info
        self._save_bans()
        return True

    def unban_user(self, user_id: int) -> bool:
        """
        Разбанивает пользователя
        :param user_id: ID пользователя
        :return: True если успешно, False если не был забанен
        """
        user_id_str = str(user_id)
        if user_id_str in self.bans:
            del self.bans[user_id_str]
            self._save_bans()
            return True
        return False

    def is_banned(self, user_id: int) -> bool:
        """
        Проверяет, забанен ли пользователь
        :param user_id: ID пользователя
        :return: True если забанен
        """
        user_id_str = str(user_id)
        if user_id_str not in self.bans:
            return False

        ban_info = self.bans[user_id_str]

        # Проверяем, не истек ли срок бана
        if ban_info['expires_at'] and ban_info['expires_at'] < datetime.now():
            # Автоматически разбаниваем
            del self.bans[user_id_str]
            self._save_bans()
            return False

        return True

    def get_ban_info(self, user_id: int) -> Optional[Dict]:
        """
        Получает информацию о бане пользователя
        :param user_id: ID пользователя
        :return: информация о бане или None
        """
        user_id_str = str(user_id)
        if self.is_banned(user_id):
            return self.bans[user_id_str]
        return None

    def get_all_bans(self) -> Dict:
        """Возвращает список всех активных банов"""
        # Очищаем истекшие баны
        to_remove = []
        for user_id_str, ban_info in self.bans.items():
            if ban_info['expires_at'] and ban_info['expires_at'] < datetime.now():
                to_remove.append(user_id_str)

        for user_id_str in to_remove:
            del self.bans[user_id_str]

        if to_remove:
            self._save_bans()

        return self.bans

    def get_ban_stats(self) -> Dict:
        """Возвращает статистику по банам"""
        bans = self.get_all_bans()
        permanent = sum(1 for ban in bans.values() if ban.get('permanent', False))
        temporary = len(bans) - permanent

        return {
            'total_bans': len(bans),
            'permanent_bans': permanent,
            'temporary_bans': temporary
        }

    def clear_expired_bans(self):
        """Очищает истекшие баны"""
        to_remove = []
        for user_id_str, ban_info in self.bans.items():
            if ban_info['expires_at'] and ban_info['expires_at'] < datetime.now():
                to_remove.append(user_id_str)

        for user_id_str in to_remove:
            del self.bans[user_id_str]

        if to_remove:
            self._save_bans()

        return len(to_remove)


# Класс для декоратора проверки бана
class BanDecorator:
    def __init__(self, ban_system: BanSystem):
        self.ban_system = ban_system

    def check_ban(self, func):
        """Декоратор для проверки бана перед выполнением функции"""

        def wrapper(message, *args, **kwargs):
            if self.ban_system.is_banned(message.from_user.id):
                ban_info = self.ban_system.get_ban_info(message.from_user.id)

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


# Создаем глобальный экземпляр системы банов
ban_system = BanSystem()


# Функция для быстрой проверки бана
def is_user_banned(user_id: int) -> bool:
    """Быстрая проверка бана пользователя"""
    return ban_system.is_banned(user_id)


# Функция для бана через команду
def ban_user_command(bot, message):
    """Обработчик команды /ban"""
    try:
        # Проверяем, что команда в группе
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "❌ Эта команда доступна только в группах")
            return

        # Проверяем, что ответили на сообщение
        if not message.reply_to_message:
            bot.reply_to(message, "❌ Используйте команду /ban в ответ на сообщение пользователя")
            return

        # Получаем ID пользователя для бана
        banned_user = message.reply_to_message.from_user
        admin_user = message.from_user

        # Разбираем аргументы команды
        args = message.text.split()
        duration = None
        reason = ""

        if len(args) > 1:
            # Проверяем, есть ли длительность (формат: 1h, 24h, 7d)
            import re
            duration_match = re.match(r'(\d+)([hd])', args[1])
            if duration_match:
                value = int(duration_match.group(1))
                unit = duration_match.group(2)
                if unit == 'h':
                    duration = value
                elif unit == 'd':
                    duration = value * 24
                reason = ' '.join(args[2:]) if len(args) > 2 else ""
            else:
                reason = ' '.join(args[1:])

        # Баним пользователя
        success = ban_system.ban_user(
            user_id=banned_user.id,
            admin_id=admin_user.id,
            reason=reason,
            duration=duration
        )

        if success:
            duration_text = f" на {duration}ч" if duration else " навсегда"
            bot.reply_to(
                message,
                f"✅ Пользователь {banned_user.full_name} забанен{duration_text}.\n"
                f"Причина: {reason or 'Не указана'}"
            )

            # Уведомляем пользователя о бане
            try:
                ban_info = ban_system.get_ban_info(banned_user.id)
                if duration:
                    expires = ban_info['expires_at'].strftime('%d.%m.%Y %H:%M')
                    bot.send_message(
                        banned_user.id,
                        f"⛔ Вы были забанены в группе до {expires}\n"
                        f"Причина: {reason or 'Не указана'}"
                    )
                else:
                    bot.send_message(
                        banned_user.id,
                        f"⛔ Вы были забанены в группе навсегда\n"
                        f"Причина: {reason or 'Не указана'}"
                    )
            except:
                pass  # Пользователь заблокировал бота
        else:
            bot.reply_to(message, "❌ Пользователь уже забанен")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


# Функция для разбана через команду
def unban_user_command(bot, message):
    """Обработчик команды /unban"""
    try:
        # Проверяем, что команда в группе
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "❌ Эта команда доступна только в группах")
            return

        # Проверяем, что ответили на сообщение
        if not message.reply_to_message:
            bot.reply_to(message, "❌ Используйте команду /unban в ответ на сообщение пользователя")
            return

        # Получаем ID пользователя для разбана
        unbanned_user = message.reply_to_message.from_user

        # Разбаниваем пользователя
        success = ban_system.unban_user(unbanned_user.id)

        if success:
            bot.reply_to(
                message,
                f"✅ Пользователь {unbanned_user.full_name} разбанен"
            )

            # Уведомляем пользователя о разбане
            try:
                bot.send_message(
                    unbanned_user.id,
                    "✅ Вы были разбанены в группе"
                )
            except:
                pass  # Пользователь заблокировал бота
        else:
            bot.reply_to(message, "❌ Пользователь не находится в бане")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


# Функция для списка банов
def ban_list_command(bot, message):
    """Обработчик команды /banlist"""
    try:
        # Проверяем, что команда в группе
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "❌ Эта команда доступна только в группах")
            return

        bans = ban_system.get_all_bans()
        stats = ban_system.get_ban_stats()

        if not bans:
            bot.reply_to(message, "📝 Список банов пуст")
            return

        response = f"📋 Список банов (всего: {stats['total_bans']}):\n"
        response += f"• Навсегда: {stats['permanent_bans']}\n"
        response += f"• Временные: {stats['temporary_bans']}\n\n"

        for user_id_str, ban_info in list(bans.items())[:10]:  # Показываем только первые 10
            user_id = int(user_id_str)
            if ban_info['permanent']:
                expiry = "Навсегда"
            else:
                expiry = ban_info['expires_at'].strftime('%d.%m.%Y %H:%M')

            response += f"👤 ID: {user_id}\n"
            response += f"⏰ До: {expiry}\n"
            if ban_info['reason']:
                response += f"📝 Причина: {ban_info['reason']}\n"
            response += "\n"

        if len(bans) > 10:
            response += f"... и еще {len(bans) - 10} банов"

        bot.reply_to(message, response)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")