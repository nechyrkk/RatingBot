from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from data import INSTITUTES

# ------------- Reply-клавиатуры -------------
def get_main_keyboard(has_profile: bool = False):
    if has_profile:
        buttons = [
            [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Редактировать анкету")],
            [KeyboardButton(text="Просмотр анкет"), KeyboardButton(text="Мой рейтинг")],
            [KeyboardButton(text="Топ встреч"), KeyboardButton(text="Удалить анкету")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="Создать анкету")],
            [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Редактировать анкету")],
            [KeyboardButton(text="Просмотр анкет"), KeyboardButton(text="Мой рейтинг")],
            [KeyboardButton(text="Топ встреч"), KeyboardButton(text="Удалить анкету")]
        ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_admin_keyboard():
    buttons = [
        [KeyboardButton(text="Создать анкету")],
        [KeyboardButton(text="Моя анкета"), KeyboardButton(text="Редактировать анкету")],
        [KeyboardButton(text="Просмотр анкет"), KeyboardButton(text="Статистика"), KeyboardButton(text="Мой рейтинг")],
        [KeyboardButton(text="Топ встреч"), KeyboardButton(text="Удалить анкету")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_edit_keyboard():
    buttons = [
        [KeyboardButton(text="Изменить имя"), KeyboardButton(text="Изменить возраст")],
        [KeyboardButton(text="Изменить пол"), KeyboardButton(text="Изменить интересы")],
        [KeyboardButton(text="Изменить институт"), KeyboardButton(text="Изменить описание")],
        [KeyboardButton(text="Изменить фото")],
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

def get_institute_keyboard():
    buttons = []
    for i in range(0, len(INSTITUTES), 2):
        row = [KeyboardButton(text=inst) for inst in INSTITUTES[i:i+2]]
        buttons.append(row)
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_done_keyboard():
    button = KeyboardButton(text="Готово")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

def get_back_keyboard():
    button = KeyboardButton(text="Назад в меню")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)

remove_keyboard = ReplyKeyboardRemove()

# ------------- Inline-клавиатуры -------------
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

def get_meet_keyboard(offer_id: int, user_id: int, other_id: int):
    """Клавиатура для предложения встречи (сейчас не используется, но оставим для совместимости)"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Я там", callback_data=f"meet_accept_{offer_id}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"meet_decline_{offer_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_rating_keyboard(target_id: int):
    buttons = []
    row = []
    for i in range(1, 6):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"rate_{i}_{target_id}"))
    buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)