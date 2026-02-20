# keyboards.py
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="Создать анкету")],
        [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Редактировать анкету")],
        [KeyboardButton(text="Просмотр анкет"), KeyboardButton(text="Мой рейтинг")],
        [KeyboardButton(text="Удалить анкету")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    buttons = [
        [KeyboardButton(text="Создать анкету")],
        [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Редактировать анкету")],
        [KeyboardButton(text="Просмотр анкет"), KeyboardButton(text="Статистика"), KeyboardButton(text="Мой рейтинг")],
        [KeyboardButton(text="Удалить анкету")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_edit_keyboard():
    buttons = [
        [KeyboardButton(text="Изменить имя"), KeyboardButton(text="Изменить возраст")],
        [KeyboardButton(text="Изменить пол"), KeyboardButton(text="Изменить интересы")],
        [KeyboardButton(text="Изменить описание"), KeyboardButton(text="Изменить фото")],
        [KeyboardButton(text="Пересоздать анкету")],
        [KeyboardButton(text="Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_gender_keyboard():
    buttons = [
        [KeyboardButton(text="Парень"), KeyboardButton(text="Девушка")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_interests_keyboard():
    buttons = [
        [KeyboardButton(text="Парни"), KeyboardButton(text="Девушки")],
        [KeyboardButton(text="Все")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_done_keyboard():
    button = KeyboardButton(text="Готово")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

def get_back_keyboard():
    button = KeyboardButton(text="Назад в меню")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

remove_keyboard = ReplyKeyboardRemove()

def get_like_dislike_superlike_keyboard(owner_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like_{owner_id}"),
            InlineKeyboardButton(text="⭐ Суперлайк", callback_data=f"superlike_{owner_id}"),
            InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"dislike_{owner_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_reply_keyboard(liker_id: int):
    buttons = [
        [
            InlineKeyboardButton(text="❤️ Ответить лайком", callback_data=f"reply_like_{liker_id}"),
            InlineKeyboardButton(text="👎 Дизлайк", callback_data=f"reply_dislike_{liker_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_delete_confirm_keyboard():
    buttons = [
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data="delete_confirm"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="delete_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# НОВАЯ КЛАВИАТУРА ДЛЯ ОЦЕНКИ ПОСЛЕ МЕТЧА
def get_rating_keyboard(target_id: int):
    """Инлайн-клавиатура с оценками 1-5 (звёздочки)"""
    buttons = [
        [
            InlineKeyboardButton(text="1⭐", callback_data=f"rate_1_{target_id}"),
            InlineKeyboardButton(text="2⭐", callback_data=f"rate_2_{target_id}"),
            InlineKeyboardButton(text="3⭐", callback_data=f"rate_3_{target_id}"),
            InlineKeyboardButton(text="4⭐", callback_data=f"rate_4_{target_id}"),
            InlineKeyboardButton(text="5⭐", callback_data=f"rate_5_{target_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)