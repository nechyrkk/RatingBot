import os
import random
import datetime
import logging
import aiosqlite  # <-- добавлено
from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError
from states import EditProfile

from data import (
    get_profile, create_meet_task, get_meet_task_by_id,
    update_meet_task_status, add_points, get_active_meet_task_for_user,
    update_meet_agreement, DB_PATH, award_badge, get_seasonal_info
)
import config

router = Router()

SAFE_LOCATIONS = [
    "Основная столовка",
    "Коворкинг",
    "Турникеты у входа",
    "Вход в спортзал",
    "Юнифуд около входа",
    "Юнифуд под лестницей",
    "Гардеробная главная",
    "Гардеробная нижняя",
]

def generate_location(institute: str) -> str:
    return random.choice(SAFE_LOCATIONS)

async def create_meet_after_like(bot: Bot, user1_id: int, user2_id: int, initiator_id: int):
    """
    Создаёт предложение встречи после взаимного лайка.
    Отправляет обоим пользователям кнопки для согласия/отказа.
    """
    profile1 = await get_profile(user1_id)
    profile2 = await get_profile(user2_id)
    if not profile1 or not profile2:
        return

    institute1 = profile1.get('institute')
    institute2 = profile2.get('institute')
    if institute1 != institute2:
        return  # разные институты — встречу не предлагаем

    location = generate_location(institute1)
    deadline = datetime.datetime.now() + datetime.timedelta(hours=24)

    # Создаём задание со статусом pending
    task_id = await create_meet_task(user1_id, user2_id, initiator_id, institute1, location, deadline)

    # Создаём инлайн-клавиатуру для каждого
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Пойти на встречу", callback_data=f"meet_agree_{task_id}"),
            InlineKeyboardButton(text="❌ Отказаться", callback_data=f"meet_decline_{task_id}")
        ]
    ])

    # Отправляем сообщения и сохраняем ID сообщений в задании
    msg1 = await bot.send_message(
        user1_id,
        f"🎉 У вас взаимная симпатия с {profile2['name']}! "
        f"Хотите встретиться в {location} в вашем институте?",
        reply_markup=keyboard
    )
    msg2 = await bot.send_message(
        user2_id,
        f"🎉 У вас взаимная симпатия с {profile1['name']}! "
        f"Хотите встретиться в {location} в вашем институте?",
        reply_markup=keyboard
    )

    # Обновляем задание, добавляя ID сообщений
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE meet_tasks SET msg1_id = ?, msg2_id = ? WHERE id = ?', (msg1.message_id, msg2.message_id, task_id))
        await db.commit()

@router.callback_query(F.data.startswith("meet_agree_"))
async def meet_agree_callback(callback: CallbackQuery, bot: Bot):
    task_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    result = await update_meet_agreement(task_id, user_id, agreed=True)

    if result is None:
        await callback.answer("Задание не найдено или уже обработано.", show_alert=True)
        return

    # Убираем клавиатуру у ответившего
    await callback.message.edit_reply_markup(reply_markup=None)

    if result == 'both_agreed':
        # Оба согласились — активируем этап видео
        task = await get_meet_task_by_id(task_id)
        if task:
            # Определяем инициатора
            if task['initiator_id'] == task['user1_id']:
                initiator_id = task['user1_id']
                other_id = task['user2_id']
            else:
                initiator_id = task['user2_id']
                other_id = task['user1_id']

            # Убираем клавиатуру у второго пользователя (если она ещё есть)
            try:
                await bot.edit_message_reply_markup(
                    chat_id=other_id,
                    message_id=task['msg2_id'] if other_id == task['user2_id'] else task['msg1_id'],
                    reply_markup=None
                )
            except Exception as e:
                logging.warning(f"Не удалось убрать клавиатуру у {other_id}: {e}")

            # Отправляем инициатору задание на видео
            await bot.send_message(
                initiator_id,
                f"🎉 Оба согласились на встречу! Вы должны в течение 24 часов отправить в этот чат видеосообщение (кружок) с места встречи {task['location']}. После этого администратор проверит и начислит очки."
            )
            initiator_profile = await get_profile(initiator_id)
            initiator_name = initiator_profile['name'] if initiator_profile else "Участник"
            await bot.send_message(
                other_id,
                f"🎉 Оба согласились на встречу! Ожидайте, {initiator_name} отправит видео для подтверждения."
            )
        await callback.answer("Вы согласились на встречу! Ожидаем ответ второго участника.")
    elif result == 'agreed':
        await callback.answer("Вы согласились на встречу! Ожидаем ответ второго участника.")
    elif result == 'declined':
        # Этот случай не должен произойти при agreed=True, но на всякий случай
        await callback.answer("Ошибка.")
    else:
        await callback.answer("Что-то пошло не так.")

@router.callback_query(F.data.startswith("meet_decline_"))
async def meet_decline_callback(callback: CallbackQuery, bot: Bot):
    task_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id

    result = await update_meet_agreement(task_id, user_id, agreed=False)

    if result is None:
        await callback.answer("Задание не найдено или уже обработано.", show_alert=True)
        return

    # Убираем клавиатуру у ответившего
    await callback.message.edit_reply_markup(reply_markup=None)

    if result == 'declined':
        # Отказ, уведомляем обоих
        task = await get_meet_task_by_id(task_id)
        if task:
            # Получаем имена
            profile1 = await get_profile(task['user1_id'])
            profile2 = await get_profile(task['user2_id'])
            name1 = profile1['name'] if profile1 else "Пользователь"
            name2 = profile2['name'] if profile2 else "Пользователь"

            # Убираем клавиатуру у второго
            other_id = task['user2_id'] if task['user1_id'] == user_id else task['user1_id']
            try:
                await bot.edit_message_reply_markup(
                    chat_id=other_id,
                    message_id=task['msg2_id'] if other_id == task['user2_id'] else task['msg1_id'],
                    reply_markup=None
                )
            except Exception as e:
                logging.warning(f"Не удалось убрать клавиатуру у {other_id}: {e}")

            # Отправляем сообщение об отказе
            decliner_name = name1 if task['user1_id'] == user_id else name2
            await bot.send_message(
                task['user1_id'],
                f"❌ {decliner_name} отказался от встречи. Встреча отменена."
            )
            await bot.send_message(
                task['user2_id'],
                f"❌ {decliner_name} отказался от встречи. Встреча отменена."
            )
        await callback.answer("Вы отказались от встречи.")
    else:
        await callback.answer("Ошибка.")

async def handle_video_message(message: Message, bot: Bot):
    """Обработчик видеосообщений (кружков)"""
    user_id = message.from_user.id
    # Ищем активное задание, где этот пользователь инициатор и статус waiting_video
    task = await get_active_meet_task_for_user(user_id, 'waiting_video')
    if not task:
        await message.answer("У вас нет активных заданий на отправку видео.")
        return
    # Принимаем видео только от инициатора
    if task['initiator_id'] != user_id:
        return

    # Скачиваем видео на диск — video_file_id привязан к боту, ModeratorBot не сможет его переслать
    video_file_id = message.video_note.file_id
    video_path = None
    try:
        video_dir = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), 'meet_videos')
        os.makedirs(video_dir, exist_ok=True)
        video_path = os.path.join(video_dir, f'{task["id"]}.mp4')
        await bot.download(video_file_id, destination=video_path)
    except Exception as e:
        logging.warning(f"Не удалось скачать видео встречи {task['id']}: {e}")
        video_path = None

    # Сохраняем video_file_id и video_path, переводим в waiting_admin
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE meet_tasks SET status = ?, video_file_id = ?, video_path = ?, admin_notified = 0 WHERE id = ?',
            ('waiting_admin', video_file_id, video_path, task['id'])
        )
        await db.commit()

    await message.answer("Видео отправлено на проверку. Ожидайте подтверждения администратора.")

@router.message(~StateFilter(EditProfile.waiting_for_new_video), F.video_note)
async def video_note_handler(message: Message, bot: Bot):
    await handle_video_message(message, bot)

@router.callback_query(F.data.startswith("confirm_meet_"))
async def admin_confirm_meet(callback: CallbackQuery, bot: Bot):
    """Подтверждение встречи администратором"""
    task_id = int(callback.data.split("_")[2])
    task = await get_meet_task_by_id(task_id)
    if not task or task['status'] != 'waiting_admin':
        await callback.answer("Задание не найдено или уже обработано.", show_alert=True)
        return

    # Сезонный множитель
    seasonal = get_seasonal_info()
    multiplier = seasonal['multiplier']
    points = int(10 * multiplier)

    # Начисляем очки обоим пользователям
    await add_points(task['user1_id'], points)
    await add_points(task['user2_id'], points)

    # Выдаём бейдж за первую встречу
    await award_badge(task['user1_id'], 'first_meet')
    await award_badge(task['user2_id'], 'first_meet')

    # Обновляем статус
    await update_meet_task_status(task_id, 'confirmed', admin_decision=1)

    # Формируем текст уведомления
    if seasonal['name']:
        bonus_text = f" (x{multiplier} — {seasonal['name']})"
    else:
        bonus_text = ""

    # Уведомляем пользователей
    await bot.send_message(task['user1_id'], f"✅ Ваша встреча подтверждена! +{points} очков{bonus_text}")
    await bot.send_message(task['user2_id'], f"✅ Ваша встреча подтверждена! +{points} очков{bonus_text}")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Встреча подтверждена, очки начислены.")

@router.callback_query(F.data.startswith("decline_meet_"))
async def admin_decline_meet(callback: CallbackQuery, bot: Bot):
    """Отказ администратора"""
    task_id = int(callback.data.split("_")[2])
    task = await get_meet_task_by_id(task_id)
    if not task or task['status'] != 'waiting_admin':
        await callback.answer("Задание не найдено или уже обработано.", show_alert=True)
        return

    await update_meet_task_status(task_id, 'declined', admin_decision=0)

    await bot.send_message(task['user1_id'], "❌ Ваша встреча не подтверждена администратором. Очки не начислены.")
    await bot.send_message(task['user2_id'], "❌ Встреча не подтверждена.")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Встреча отклонена.")