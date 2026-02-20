import random
import datetime
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from data import (
    get_profile, create_meet_task, get_meet_task_by_id,
    update_meet_task_status, add_points, get_active_meet_task_for_user
)
import config

router = Router()

def generate_location(institute: str) -> str:
    return f"А-{random.randint(1, 16)}"

async def create_meet_after_like(bot: Bot, user1_id: int, user2_id: int, initiator_id: int):
    """
    Создаёт задание на встречу после взаимного лайка, если пользователи из одного института.
    initiator_id — кто первый лайкнул (будет отправлять видео).
    """
    profile1 = await get_profile(user1_id)
    profile2 = await get_profile(user2_id)
    if not profile1 or not profile2:
        return

    institute1 = profile1.get('institute')
    institute2 = profile2.get('institute')
    if institute1 != institute2:
        return  # разные институты — мит не предлагаем

    # Генерируем место встречи
    location = generate_location(institute1)

    # Дедлайн: через 24 часа
    deadline = datetime.datetime.now() + datetime.timedelta(hours=24)

    # Создаём задание
    task_id = await create_meet_task(user1_id, user2_id, initiator_id, institute1, location, deadline)

    # Определяем, кто инициатор
    if initiator_id == user1_id:
        initiator_name = profile1['name']
        other_name = profile2['name']
        other_id = user2_id
    else:
        initiator_name = profile2['name']
        other_name = profile1['name']
        other_id = user1_id

    # Сообщение для инициатора
    await bot.send_message(
        initiator_id,
        f"🎉 У вас взаимная симпатия с {other_name}! Чтобы получить очки, встретьтесь в институте {institute1}, место: {location}. "
        f"Вы должны в течение 24 часов отправить в этот чат видеосообщение (кружок) с места встречи. После этого администратор проверит и начислит очки."
    )

    # Сообщение для второго
    await bot.send_message(
        other_id,
        f"🎉 У вас взаимная симпатия с {initiator_name}! Для получения очков встретьтесь в институте {institute1}, место: {location}. "
        f"{initiator_name} отправит видеоподтверждение. Ожидайте."
    )

@router.message(F.video_note)
async def handle_video_message(message: Message, bot: Bot):
    """Обработчик видеосообщений (кружков)"""
    user_id = message.from_user.id
    # Ищем активное задание, где этот пользователь инициатор и статус waiting_video
    task = await get_active_meet_task_for_user(user_id, 'waiting_video')
    if not task:
        await message.answer("У вас нет активных заданий на отправку видео.")
        return

    if not config.ADMIN_IDS:
        await message.answer("Ошибка: не назначен администратор.")
        logging.error("Нет администраторов для обработки видео.")
        return

    # Пересылаем видео администратору
    admin_id = config.ADMIN_IDS[0]  # предполагаем, что хотя бы один админ есть
    forwarded = await bot.send_video_note(
        admin_id,
        message.video_note.file_id,
        caption=f"📹 Видеоподтверждение от пользователя {user_id} для задания #{task['id']}"
    )

    # Сохраняем message_id пересланного сообщения
    await update_meet_task_status(task['id'], 'waiting_admin', video_message_id=forwarded.message_id)

    # Отправляем админу инлайн-кнопки для подтверждения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_meet_{task['id']}"),
            InlineKeyboardButton(text="❌ Отказать", callback_data=f"decline_meet_{task['id']}")
        ]
    ])
    await bot.send_message(
        admin_id,
        f"Подтвердите встречу для задания #{task['id']} (пользователи: {task['user1_id']} и {task['user2_id']})",
        reply_markup=keyboard
    )

    await message.answer("Видео отправлено администратору. Ожидайте подтверждения.")

@router.callback_query(F.data.startswith("confirm_meet_"))
async def admin_confirm_meet(callback: CallbackQuery, bot: Bot):
    """Подтверждение встречи администратором"""
    await callback.answer()
    task_id = int(callback.data.split("_")[2])
    task = await get_meet_task_by_id(task_id)
    if not task or task['status'] != 'waiting_admin':
        await callback.message.answer("Задание не найдено или уже обработано.")
        return

    # Начисляем очки обоим пользователям
    await add_points(task['user1_id'], 10)
    await add_points(task['user2_id'], 10)

    # Обновляем статус
    await update_meet_task_status(task_id, 'confirmed', admin_decision=1)

    # Уведомляем пользователей
    await bot.send_message(task['user1_id'], "✅ Ваша встреча подтверждена! Вы получили 10 очков.")
    await bot.send_message(task['user2_id'], "✅ Ваша встреча подтверждена! Вы получили 10 очков.")

    # Удаляем кнопки у сообщения админа
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass

@router.callback_query(F.data.startswith("decline_meet_"))
async def admin_decline_meet(callback: CallbackQuery, bot: Bot):
    """Отказ администратора"""
    await callback.answer()
    task_id = int(callback.data.split("_")[2])
    task = await get_meet_task_by_id(task_id)
    if not task or task['status'] != 'waiting_admin':
        await callback.message.answer("Задание не найдено или уже обработано.")
        return

    await update_meet_task_status(task_id, 'declined', admin_decision=0)

    await bot.send_message(task['user1_id'], "❌ Ваша встреча не подтверждена администратором. Очки не начислены.")
    await bot.send_message(task['user2_id'], "❌ Встреча не подтверждена.")

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except:
        pass