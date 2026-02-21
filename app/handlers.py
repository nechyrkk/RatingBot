import logging
import random
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import aiosqlite
import config
from meetings import create_meet_after_like, router as meet_router
from matching import get_next_profile
from rating_system import get_user_rating, add_rating, get_voter_weight
from states import CreateProfile, EditProfile, BrowseProfiles, SuperLike
from keyboards import (
    get_main_keyboard, get_edit_keyboard, get_done_keyboard,
    get_back_keyboard, remove_keyboard, get_like_dislike_superlike_keyboard,
    get_reply_keyboard, get_gender_keyboard, get_interests_keyboard,
    get_admin_keyboard, get_delete_confirm_keyboard, get_institute_keyboard,
    get_rating_keyboard
)
from data import (
    save_profile, get_profile, get_all_profiles,
    add_like, add_dislike, get_ratings,
    get_user_stats, get_all_usernames, get_top_users,
    DB_PATH, delete_profile, INSTITUTES
)

router = Router()
router.include_router(meet_router)
MAX_PHOTOS = 3

def is_compatible(liker_gender: str, target_interests: str) -> bool:
    if target_interests == "Парни":
        return liker_gender == "Парень"
    elif target_interests == "Девушки":
        return liker_gender == "Девушка"
    elif target_interests == "Все":
        return True
    return False

# --------------------- СТАРТ ---------------------
@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = await get_profile(user_id) is not None
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer(
        "Привет! Я помогу создать анкету и найти знакомства.\n"
        "Используй кнопки ниже или команды:\n"
        "/create – создать новую анкету\n"
        "/myprofile – посмотреть свою анкету\n"
        "/edit – редактировать анкету\n"
        "/browse – просмотр анкет\n"
        "/stats – статистика (только для админа)\n"
        "/cancel – отменить действие",
        reply_markup=keyboard
    )

# --------------------- СТАТИСТИКА (ТОЛЬКО АДМИН) ---------------------
@router.message(Command("stats"))
@router.message(F.text == "Статистика")
async def cmd_stats(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id not in config.ADMIN_IDS:
        await message.answer("У вас нет прав на просмотр статистики.")
        return

    stats = await get_user_stats()
    total = stats['total']
    gender_stats = stats['gender']
    male = gender_stats.get('Парень', 0)
    female = gender_stats.get('Девушка', 0)

    all_usernames = await get_all_usernames(bot)

    male_users = []
    female_users = []

    async with aiosqlite.connect(DB_PATH) as db:
        for uid, display in all_usernames.items():
            async with db.execute('SELECT gender FROM profiles WHERE user_id = ?', (uid,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    gender = row[0]
                    rating = await get_user_rating(uid)
                    if rating == 1.0:
                        rating_display = "1⭐ (начальный)"
                    else:
                        if rating.is_integer():
                            rating_display = f"{int(rating)}⭐"
                        else:
                            rating_display = f"{rating:.2f}⭐"
                    line = f"{rating_display} {display}"
                    if gender == "Парень":
                        male_users.append(line)
                    else:
                        female_users.append(line)

    text = f"📊 **Статистика пользователей:**\n\n" \
           f"Всего анкет: {total}\n" \
           f"Парней: {male}\n" \
           f"Девушек: {female}\n\n"

    if male_users:
        text += "👤 **Парни:**\n" + "\n".join(male_users) + "\n\n"
    if female_users:
        text += "👩 **Девушки:**\n" + "\n".join(female_users)

    if len(text) > 4096:
        parts = [text[i:i + 4096] for i in range(0, len(text), 4096)]
        for part in parts:
            try:
                await message.answer(part, parse_mode="Markdown")
            except Exception:
                await message.answer(part, parse_mode=None)
    else:
        try:
            await message.answer(text, parse_mode=None)
        except Exception:
            await message.answer(text, parse_mode=None)

# --------------------- ТОП ВСТРЕЧ ---------------------
@router.message(F.text == "Топ встреч")
async def cmd_top_meets(message: Message):
    top_users = await get_top_users(limit=10)
    if not top_users:
        await message.answer("Пока никто не участвовал во встречах в этом месяце.")
        return

    lines = []
    for idx, (uid, points) in enumerate(top_users, 1):
        profile = await get_profile(uid)
        name = profile['name'] if profile else f"Пользователь {uid}"
        lines.append(f"{idx}. {name} — {points} очков")

    text = "🏆 **Топ встреч за текущий месяц:**\n\n" + "\n".join(lines)
    await message.answer(text, parse_mode="Markdown")

# --------------------- ОТМЕНА ---------------------
@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного действия.")
        return
    await state.clear()
    user_id = message.from_user.id
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = await get_profile(user_id) is not None
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Действие отменено.", reply_markup=keyboard)

@router.message(F.text == "Назад в меню")
async def back_to_menu_general(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = await get_profile(user_id) is not None
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Главное меню", reply_markup=keyboard)

# --------------------- СОЗДАНИЕ АНКЕТЫ ---------------------
@router.message(Command("create"))
@router.message(F.text == "Создать анкету")
async def cmd_create(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await get_profile(user_id):
        await message.answer("У вас уже есть анкета. Используйте /edit для редактирования.")
        return
    await state.set_state(CreateProfile.waiting_for_name)
    await message.answer(
        "Давай создадим анкету!\n"
        "Введите ваше имя:",
        reply_markup=remove_keyboard
    )

@router.message(CreateProfile.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Имя не может быть пустым. Попробуйте снова.")
        return
    await state.update_data(name=name)
    await state.set_state(CreateProfile.waiting_for_age)
    await message.answer("Сколько вам лет?")

@router.message(CreateProfile.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age <= 0 or age > 120:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный возраст (число от 1 до 120).")
        return
    await state.update_data(age=age)
    await state.set_state(CreateProfile.waiting_for_gender)
    await message.answer("Выберите ваш пол:", reply_markup=get_gender_keyboard())

@router.message(CreateProfile.waiting_for_gender, F.text.in_(["Парень", "Девушка"]))
async def process_gender(message: Message, state: FSMContext):
    gender = message.text
    await state.update_data(gender=gender)
    await state.set_state(CreateProfile.waiting_for_interests)
    await message.answer("Кто вас интересует?", reply_markup=get_interests_keyboard())

@router.message(CreateProfile.waiting_for_interests, F.text.in_(["Парни", "Девушки", "Все"]))
async def process_interests(message: Message, state: FSMContext):
    interests = message.text
    await state.update_data(interests=interests)
    await state.set_state(CreateProfile.waiting_for_institute)
    await message.answer("Выберите ваш институт:", reply_markup=get_institute_keyboard())

@router.message(CreateProfile.waiting_for_institute, F.text.in_(INSTITUTES))
async def process_institute(message: Message, state: FSMContext):
    institute = message.text
    await state.update_data(institute=institute)
    await state.set_state(CreateProfile.waiting_for_description)
    await message.answer("Напишите описание о себе:", reply_markup=remove_keyboard)

@router.message(CreateProfile.waiting_for_institute)
async def handle_invalid_institute(message: Message):
    await message.answer("Пожалуйста, выберите институт из списка кнопок.", reply_markup=get_institute_keyboard())

@router.message(CreateProfile.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if not description:
        await message.answer("Описание не может быть пустым.")
        return
    await state.update_data(description=description, photos=[])
    await state.set_state(CreateProfile.waiting_for_photos)
    await message.answer(
        "Теперь загрузите фотографии (до 3). Можно отправлять по одной.\n"
        "Когда закончите, нажмите кнопку 'Готово'.",
        reply_markup=get_done_keyboard()
    )

@router.message(CreateProfile.waiting_for_photos, F.photo)
async def process_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photos = data.get('photos', [])
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    if len(photos) >= MAX_PHOTOS:
        await finish_creation(message, state, bot)
    else:
        await message.answer(f"Фото добавлено ({len(photos)}/{MAX_PHOTOS}). Можете добавить ещё или нажать 'Готово'.")

@router.message(CreateProfile.waiting_for_photos, F.text.casefold() == "готово")
@router.message(CreateProfile.waiting_for_photos, Command("done"))
async def done_photos(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photos = data.get('photos', [])
    if not photos:
        await message.answer("Вы не загрузили ни одного фото. Пожалуйста, отправьте хотя бы одну фотографию.")
        return
    await finish_creation(message, state, bot)

async def finish_creation(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    name = data['name']
    age = data['age']
    gender = data['gender']
    interests = data['interests']
    institute = data.get('institute', 'ИИТ')
    description = data['description']
    photos = data['photos']

    user_id = message.from_user.id
    await save_profile(user_id, name, age, gender, interests, institute, description, photos)

    await state.clear()
    await show_profile(message, user_id, edit_mode=False)

# --------------------- ПРОСМОТР СВОЕЙ АНКЕТЫ ---------------------
@router.message(Command("myprofile"))
@router.message(F.text == "Моя анкета")
async def cmd_myprofile(message: Message):
    user_id = message.from_user.id
    await show_profile(message, user_id, edit_mode=False)

async def show_profile(message: Message, user_id: int, edit_mode: bool = False):
    profile = await get_profile(user_id)
    if not profile:
        await message.answer("У вас ещё нет анкеты. Создайте её командой /create или нажмите 'Создать анкету'.")
        return

    name = profile['name']
    age = profile['age']
    description = profile['description']
    photos = profile.get('photos', [])

    text = f"📝 **Ваша анкета:**\nИмя: {name}\nВозраст: {age}\nОписание: {description}"

    try:
        if not photos:
            await message.answer(text, parse_mode="Markdown")
        elif len(photos) == 1:
            await message.answer_photo(photo=photos[0], caption=text, parse_mode="Markdown")
        else:
            media_group = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))
            await message.answer_media_group(media=media_group)
    except TelegramBadRequest as e:
        logging.error(f"Ошибка отправки фото для user {user_id}: {e}")
        await message.answer(f"{text}\n\n⚠️ Некоторые фото повреждены, обновите их.", parse_mode="Markdown")
        profile['photos'] = []
        await save_profile(user_id, name, age, profile['gender'], profile['interests'], profile['institute'], description, [])

    if not edit_mode:
        is_admin = (user_id in config.ADMIN_IDS)
        has_profile = True
        keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
        await message.answer("Что хотите сделать дальше?", reply_markup=keyboard)

# --------------------- РЕДАКТИРОВАНИЕ ---------------------
@router.message(Command("edit"))
@router.message(F.text == "Редактировать анкету")
async def cmd_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await message.answer("Сначала создайте анкету.", reply_markup=get_main_keyboard(False))
        return

    await state.set_state(EditProfile.choosing_field)
    await message.answer("Выберите, что хотите изменить:", reply_markup=get_edit_keyboard())

@router.message(EditProfile.choosing_field, F.text.in_([
    "Изменить имя", "Изменить возраст", "Изменить пол", "Изменить интересы",
    "Изменить описание", "Изменить фото", "Изменить институт",
    "Пересоздать анкету", "Назад"
]))
async def process_edit_choice(message: Message, state: FSMContext):
    choice = message.text

    if choice == "Назад":
        await state.clear()
        user_id = message.from_user.id
        is_admin = (user_id in config.ADMIN_IDS)
        has_profile = True
        keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
        await message.answer("Главное меню", reply_markup=keyboard)
        return

    if choice == "Пересоздать анкету":
        await state.clear()
        await cmd_create(message, state)
        return

    if choice == "Изменить имя":
        await state.set_state(EditProfile.waiting_for_new_name)
        await message.answer("Введите новое имя:", reply_markup=remove_keyboard)
    elif choice == "Изменить возраст":
        await state.set_state(EditProfile.waiting_for_new_age)
        await message.answer("Введите новый возраст:", reply_markup=remove_keyboard)
    elif choice == "Изменить пол":
        await state.set_state(EditProfile.waiting_for_new_gender)
        await message.answer("Выберите ваш пол:", reply_markup=get_gender_keyboard())
    elif choice == "Изменить интересы":
        await state.set_state(EditProfile.waiting_for_new_interests)
        await message.answer("Кто вас интересует?", reply_markup=get_interests_keyboard())
    elif choice == "Изменить описание":
        await state.set_state(EditProfile.waiting_for_new_description)
        await message.answer("Введите новое описание:", reply_markup=remove_keyboard)
    elif choice == "Изменить фото":
        await state.set_state(EditProfile.waiting_for_new_photos)
        await state.update_data(new_photos=[])
        await message.answer(
            "Загрузите новые фотографии (до 3). Можно отправлять по одной. Когда закончите, нажмите 'Готово'.",
            reply_markup=get_done_keyboard()
        )
    elif choice == "Изменить институт":
        await state.set_state(EditProfile.waiting_for_new_institute)
        await message.answer("Выберите новый институт:", reply_markup=get_institute_keyboard())

# ---- Обработчики изменения полей ----
@router.message(EditProfile.waiting_for_new_name)
async def process_new_name(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if not new_name:
        await message.answer("Имя не может быть пустым. Попробуйте снова.")
        return

    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['name'] = new_name
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Имя обновлено!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_age)
async def process_new_age(message: Message, state: FSMContext):
    try:
        new_age = int(message.text)
        if new_age <= 0 or new_age > 120:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректный возраст (число от 1 до 120).")
        return

    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['age'] = new_age
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Возраст обновлён!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_gender, F.text.in_(["Парень", "Девушка"]))
async def process_new_gender(message: Message, state: FSMContext):
    new_gender = message.text
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['gender'] = new_gender
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Пол обновлён!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_interests, F.text.in_(["Парни", "Девушки", "Все"]))
async def process_new_interests(message: Message, state: FSMContext):
    new_interests = message.text
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['interests'] = new_interests
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Интересы обновлены!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_description)
async def process_new_description(message: Message, state: FSMContext):
    new_description = message.text.strip()
    if not new_description:
        await message.answer("Описание не может быть пустым. Попробуйте снова.")
        return

    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['description'] = new_description
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Описание обновлено!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_institute, F.text.in_(INSTITUTES))
async def process_new_institute(message: Message, state: FSMContext):
    new_institute = message.text
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['institute'] = new_institute
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Институт обновлён!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

@router.message(EditProfile.waiting_for_new_institute)
async def handle_invalid_new_institute(message: Message):
    await message.answer("Пожалуйста, выберите институт из списка кнопок.", reply_markup=get_institute_keyboard())

@router.message(EditProfile.waiting_for_new_photos, F.photo)
async def process_new_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    new_photos = data.get('new_photos', [])
    file_id = message.photo[-1].file_id
    new_photos.append(file_id)
    await state.update_data(new_photos=new_photos)
    if len(new_photos) >= MAX_PHOTOS:
        await finish_edit_photos(message, state)
    else:
        await message.answer(f"Фото добавлено ({len(new_photos)}/{MAX_PHOTOS}). Можете добавить ещё или нажать 'Готово'.")

@router.message(EditProfile.waiting_for_new_photos, F.text.casefold() == "готово")
@router.message(EditProfile.waiting_for_new_photos, Command("done"))
async def done_edit_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    new_photos = data.get('new_photos', [])
    if not new_photos:
        await message.answer("Вы не загрузили ни одного фото. Операция отменена.", reply_markup=get_main_keyboard(True))
        await state.clear()
        return
    await finish_edit_photos(message, state)

async def finish_edit_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    new_photos = data.get('new_photos', [])
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await state.clear()
        await message.answer("Ошибка. Анкета не найдена.", reply_markup=get_main_keyboard(False))
        return

    profile['photos'] = new_photos
    await save_profile(user_id, profile['name'], profile['age'], profile['gender'],
                       profile['interests'], profile['institute'],
                       profile['description'], profile['photos'])

    await state.clear()
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = True
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Фотографии обновлены!", reply_markup=keyboard)
    await show_profile(message, user_id, edit_mode=True)

# --------------------- УДАЛЕНИЕ АНКЕТЫ ---------------------
@router.message(F.text == "Удалить анкету")
async def cmd_delete_profile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    profile = await get_profile(user_id)
    if not profile:
        await message.answer("У вас ещё нет анкеты, нечего удалять.")
        return
    await state.clear()
    await message.answer(
        "Вы уверены, что хотите удалить свою анкету? Это действие необратимо.",
        reply_markup=get_delete_confirm_keyboard()
    )

@router.callback_query(F.data == "delete_confirm")
async def confirm_delete(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await delete_profile(user_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Ваша анкета удалена.")
    await callback.answer()

@router.callback_query(F.data == "delete_cancel")
async def cancel_delete(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Удаление отменено.")
    await callback.answer()

# --------------------- ПРОСМОТР АНКЕТ ДРУГИХ ПОЛЬЗОВАТЕЛЕЙ ---------------------
@router.message(Command("browse"))
@router.message(F.text == "Просмотр анкет")
async def cmd_browse(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not await get_profile(user_id):
        await message.answer("Сначала создайте свою анкету.", reply_markup=get_main_keyboard(False))
        return

    current_state = await state.get_state()
    data = await state.get_data()
    current_profile_id = data.get('current_profile_id')

    # Если уже в режиме просмотра и есть текущая анкета – просто напоминаем, не показываем повторно
    if current_state == BrowseProfiles.browsing and current_profile_id:
        await message.answer("Вы уже просматриваете анкету. Оцените её или нажмите 'Назад в меню'.")
        return

    # Если состояние есть, но current_profile_id отсутствует (аномалия) – перезапускаем просмотр
    if current_state == BrowseProfiles.browsing and not current_profile_id:
        # Очищаем состояние и начинаем заново
        await state.clear()

    # Начинаем новый просмотр
    await state.set_state(BrowseProfiles.browsing)
    await state.update_data(
        new_pool=[],
        disliked_pool=[],
        current_pool='new',
        current_profile_id=None,
        last_message_id=None
    )
    await message.answer(
        "Начинаем просмотр анкет. Для возврата в меню нажмите кнопку ниже.",
        reply_markup=get_back_keyboard()
    )
    await show_next_profile(message, user_id, state)


async def show_profile_by_id(target_message: Message, profile_id: int, state: FSMContext):
    """Показывает анкету с заданным ID, обновляет состояние."""
    profile = await get_profile(profile_id)
    if not profile:
        # Если анкета исчезла, переходим к следующей
        await show_next_profile(target_message, target_message.from_user.id, state)
        return

    name = profile['name']
    age = profile['age']
    description = profile['description']
    photos = profile.get('photos', [])

    text = f"👤 **Анкета:**\nИмя: {name}\nВозраст: {age}\nОписание: {description}"

    try:
        if not photos:
            sent = await target_message.answer(
                text,
                parse_mode="Markdown",
                reply_markup=get_like_dislike_superlike_keyboard(profile_id)
            )
            await state.update_data(last_message_id=sent.message_id)
        elif len(photos) == 1:
            sent = await target_message.answer_photo(
                photo=photos[0],
                caption=text,
                parse_mode="Markdown",
                reply_markup=get_like_dislike_superlike_keyboard(profile_id)
            )
            await state.update_data(last_message_id=sent.message_id)
        else:
            # Отправляем медиагруппу
            media_group = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))
            await target_message.answer_media_group(media=media_group)
            # Отдельное сообщение с кнопками
            sent = await target_message.answer(
                "Оцените анкету:",
                reply_markup=get_like_dislike_superlike_keyboard(profile_id)
            )
            await state.update_data(last_message_id=sent.message_id)
    except TelegramBadRequest as e:
        logging.error(f"Ошибка отправки фото анкеты {profile_id}: {e}")
        sent = await target_message.answer(
            text + "\n\n⚠️ Фото временно недоступно.",
            parse_mode="Markdown",
            reply_markup=get_like_dislike_superlike_keyboard(profile_id)
        )
        await state.update_data(last_message_id=sent.message_id)

    # Сохраняем ID текущей анкеты
    await state.update_data(current_profile_id=profile_id)


async def show_next_profile(target_message: Message, user_id: int, state: FSMContext):
    data = await state.get_data()
    # Удаляем предыдущее сообщение с кнопками, если оно есть
    last_msg_id = data.get('last_message_id')
    if last_msg_id:
        try:
            await target_message.bot.delete_message(chat_id=target_message.chat.id, message_id=last_msg_id)
        except Exception as e:
            logging.warning(f"Не удалось удалить предыдущее сообщение: {e}")

    next_id, updated_data = await get_next_profile(user_id, data)
    if next_id is None:
        await target_message.answer(
            "Больше нет анкет, соответствующих вашим интересам. Попробуйте позже или измените настройки."
        )
        await state.clear()
        return
    await state.update_data(**updated_data)
    await show_profile_by_id(target_message, next_id, state)

# --------------------- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ АНКЕТЫ ---------------------
async def send_profile_to_user(bot: Bot, to_user_id: int, profile: dict, custom_text: str = None):
    name = profile['name']
    age = profile['age']
    description = profile['description']
    photos = profile.get('photos', [])

    if custom_text:
        header = f"💌 {custom_text}\n\n"
    else:
        header = ""

    text = f"{header}👤 **Анкета:**\nИмя: {name}\nВозраст: {age}\nОписание: {description}"

    try:
        if not photos:
            await bot.send_message(to_user_id, text, parse_mode="Markdown")
        elif len(photos) == 1:
            await bot.send_photo(to_user_id, photo=photos[0], caption=text, parse_mode="Markdown")
        else:
            media_group = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))
            await bot.send_media_group(to_user_id, media=media_group)
    except TelegramBadRequest as e:
        logging.error(f"Ошибка отправки фото пользователю {to_user_id}: {e}")
        await bot.send_message(to_user_id, text, parse_mode="Markdown")
    except TelegramForbiddenError:
        logging.warning(f"User {to_user_id} has blocked the bot. Cannot send profile.")
    except Exception as e:
        logging.error(f"Failed to send profile to user {to_user_id}: {e}")

# --------------------- ОБРАБОТКА РЕАКЦИЙ ---------------------
@router.callback_query(BrowseProfiles.browsing, F.data.startswith(("like_", "dislike_", "superlike_")))
async def handle_reaction(callback: CallbackQuery, state: FSMContext, bot: Bot):
    action, target_id_str = callback.data.split("_")
    target_id = int(target_id_str)
    user_id = callback.from_user.id

    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "like":
        await add_like(user_id, target_id)
        target_profile = await get_profile(target_id)
        user_profile = await get_profile(user_id)
        if target_profile and user_profile and is_compatible(user_profile['gender'], target_profile['interests']):
            target_ratings = await get_ratings(target_id)
            if user_id in target_ratings['liked']:
                await notify_mutual_like(bot, user_id, target_id)
            else:
                await send_like_notification(bot, user_id, target_id)
        await callback.answer("Лайк сохранён")
        await state.update_data(current_profile_id=None, last_message_id=None)
        await show_next_profile(callback.message, user_id, state)

    elif action == "dislike":
        await add_dislike(user_id, target_id)
        await callback.answer("Дизлайк сохранён")
        await state.update_data(current_profile_id=None, last_message_id=None)
        await show_next_profile(callback.message, user_id, state)


    elif action == "superlike":

        # Убираем клавиатуру у текущего сообщения

        await callback.message.edit_reply_markup(reply_markup=None)

        # Сохраняем ID цели для следующего шага

        await state.update_data(superlike_target=target_id)

        # Сбрасываем информацию о текущей анкете, чтобы она считалась обработанной

        await state.update_data(current_profile_id=None, last_message_id=None)

        # Переводим пользователя в состояние ожидания сообщения для суперлайка

        await state.set_state(SuperLike.waiting_for_message)

        # Отправляем запрос на ввод сообщения

        await callback.message.answer(

            "Вы выбрали суперлайк! Напишите сообщение, которое получит этот пользователь вместе с вашей анкетой:"

        )

        await callback.answer()

        # Подтверждаем нажатие кнопки
        await callback.answer()

@router.message(SuperLike.waiting_for_message)
@router.message(SuperLike.waiting_for_message)
async def process_superlike_message(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get('superlike_target')
    if not target_id:
        await state.clear()
        await message.answer("Произошла ошибка. Попробуйте снова.")
        return

    user_id = message.from_user.id
    super_text = message.text.strip()
    if not super_text:
        await message.answer("Сообщение не может быть пустым. Отправьте текст или отмените командой /cancel")
        return

    # Сохраняем лайк
    await add_like(user_id, target_id)

    target_profile = await get_profile(target_id)
    user_profile = await get_profile(user_id)
    compatible = target_profile and user_profile and is_compatible(user_profile['gender'], target_profile['interests'])

    if compatible:
        await send_superlike_notification(bot, user_id, target_id, super_text)
        target_ratings = await get_ratings(target_id)
        if user_id in target_ratings['liked']:
            await notify_mutual_like(bot, user_id, target_id)
    else:
        await message.answer("Суперлайк сохранён (пользователь не увидит из-за настроек интересов).")

    # Очищаем состояние суперлайка и возвращаемся в режим просмотра
    await state.update_data(superlike_target=None)  # удаляем временные данные
    await state.set_state(BrowseProfiles.browsing)

    # Показываем следующую анкету
    await show_next_profile(message, user_id, state)

# --------------------- ФУНКЦИИ УВЕДОМЛЕНИЙ ---------------------
async def send_like_notification(bot: Bot, liker_id: int, target_id: int):
    liker_profile = await get_profile(liker_id)
    if not liker_profile:
        return

    name = liker_profile['name']
    age = liker_profile['age']
    description = liker_profile['description']
    photos = liker_profile.get('photos', [])

    text = f"💌 Пользователь {name} лайкнул вашу анкету!\n\n👤 **Анкета:**\nИмя: {name}\nВозраст: {age}\nОписание: {description}"

    try:
        if not photos:
            await bot.send_message(
                target_id,
                text,
                parse_mode="Markdown",
                reply_markup=get_reply_keyboard(liker_id)
            )
        elif len(photos) == 1:
            await bot.send_photo(
                target_id,
                photo=photos[0],
                caption=text,
                parse_mode="Markdown",
                reply_markup=get_reply_keyboard(liker_id)
            )
        else:
            media_group = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))
            await bot.send_media_group(target_id, media=media_group)
            await bot.send_message(
                target_id,
                "Этот пользователь лайкнул вашу анкету. Хотите ответить?",
                reply_markup=get_reply_keyboard(liker_id)
            )
    except TelegramBadRequest as e:
        logging.error(f"Ошибка отправки фото в like-уведомлении: {e}")
        await bot.send_message(target_id, text, parse_mode="Markdown", reply_markup=get_reply_keyboard(liker_id))
    except TelegramForbiddenError:
        logging.warning(f"User {target_id} has blocked the bot. Cannot send like notification.")
    except Exception as e:
        logging.error(f"Failed to send like notification to {target_id}: {e}")

async def send_superlike_notification(bot: Bot, liker_id: int, target_id: int, custom_message: str):
    liker_profile = await get_profile(liker_id)
    if not liker_profile:
        return

    name = liker_profile['name']
    age = liker_profile['age']
    description = liker_profile['description']
    photos = liker_profile.get('photos', [])

    text = f"💌 Пользователь {name} отправил вам суперлайк!\n\n✉️ Сообщение: {custom_message}\n\n👤 **Анкета:**\nИмя: {name}\nВозраст: {age}\nОписание: {description}"

    try:
        if not photos:
            await bot.send_message(
                target_id,
                text,
                parse_mode="Markdown",
                reply_markup=get_reply_keyboard(liker_id)
            )
        elif len(photos) == 1:
            await bot.send_photo(
                target_id,
                photo=photos[0],
                caption=text,
                parse_mode="Markdown",
                reply_markup=get_reply_keyboard(liker_id)
            )
        else:
            media_group = []
            for i, file_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=file_id, caption=text, parse_mode="Markdown"))
                else:
                    media_group.append(InputMediaPhoto(media=file_id))
            await bot.send_media_group(target_id, media=media_group)
            await bot.send_message(
                target_id,
                "Этот пользователь отправил вам суперлайк. Хотите ответить?",
                reply_markup=get_reply_keyboard(liker_id)
            )
    except TelegramBadRequest as e:
        logging.error(f"Ошибка отправки фото в superlike-уведомлении: {e}")
        await bot.send_message(target_id, text, parse_mode="Markdown", reply_markup=get_reply_keyboard(liker_id))
    except TelegramForbiddenError:
        logging.warning(f"User {target_id} has blocked the bot. Cannot send superlike notification.")
    except Exception as e:
        logging.error(f"Failed to send superlike notification to {target_id}: {e}")

async def notify_mutual_like(bot: Bot, user_id: int, target_id: int):
    user_profile = await get_profile(user_id)
    target_profile = await get_profile(target_id)
    if not user_profile or not target_profile:
        return

    await send_profile_to_user(bot, user_id, target_profile)
    await send_profile_to_user(bot, target_id, user_profile)

    try:
        target_chat = await bot.get_chat(target_id)
        target_username = target_chat.username
        contact_info = f"@{target_username}" if target_username else f"{target_profile['name']} (нет username)"
        await bot.send_message(
            user_id,
            f"💕 Взаимная симпатия! Вы можете написать пользователю {target_profile['name']}: {contact_info}"
        )
    except Exception as e:
        logging.error(f"Failed to send mutual like contact to user {user_id}: {e}")

    try:
        user_chat = await bot.get_chat(user_id)
        user_username = user_chat.username
        contact_info = f"@{user_username}" if user_username else f"{user_profile['name']} (нет username)"
        await bot.send_message(
            target_id,
            f"💕 Взаимная симпатия! Вы можете написать пользователю {user_profile['name']}: {contact_info}"
        )
    except Exception as e:
        logging.error(f"Failed to send mutual like contact to target {target_id}: {e}")

    # Предложение оценить друг друга
    await bot.send_message(
        user_id,
        f"Оцените пользователя {target_profile['name']} (от 1 до 5):",
        reply_markup=get_rating_keyboard(target_id)
    )
    await bot.send_message(
        target_id,
        f"Оцените пользователя {user_profile['name']} (от 1 до 5):",
        reply_markup=get_rating_keyboard(user_id)
    )

    # Если институты совпадают, предлагаем встречу
    if user_profile.get('institute') == target_profile.get('institute'):
        await create_meet_after_like(bot, user_id, target_id, user_id)

@router.callback_query(F.data.startswith("rate_"))
async def process_rating(callback: CallbackQuery):
    data_parts = callback.data.split("_")
    value = int(data_parts[1])
    target_id = int(data_parts[2])
    voter_id = callback.from_user.id

    if voter_id == target_id:
        await callback.answer("Нельзя оценить себя!", show_alert=True)
        return

    voter_weight = await get_voter_weight(voter_id)
    await add_rating(voter_id, target_id, value, voter_weight)

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Спасибо за оценку!")

# --------------------- ОБРАБОТКА ОТВЕТОВ НА ЛАЙКИ ---------------------
@router.callback_query(F.data.startswith(("reply_like_", "reply_dislike_")))
async def handle_reply_callback(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    action = parts[1]
    liker_id = int(parts[2])
    user_id = callback.from_user.id

    await callback.message.edit_reply_markup(reply_markup=None)

    if action == "like":
        await add_like(user_id, liker_id)
        user_profile = await get_profile(user_id)
        liker_profile = await get_profile(liker_id)
        if user_profile and liker_profile and is_compatible(liker_profile['gender'], user_profile['interests']):
            liker_ratings = await get_ratings(liker_id)
            if user_id in liker_ratings['liked']:
                await notify_mutual_like(bot, user_id, liker_id)
            else:
                await callback.answer("Вы ответили лайком!")
        else:
            await callback.answer("Лайк сохранён (пользователь не увидит)")
    else:
        await add_dislike(user_id, liker_id)
        await callback.answer("Вы ответили дизлайком.")

# --------------------- ВОЗВРАТ В МЕНЮ ИЗ РЕЖИМА ПРОСМОТРА ---------------------
@router.message(BrowseProfiles.browsing, F.text == "Назад в меню")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    is_admin = (user_id in config.ADMIN_IDS)
    has_profile = await get_profile(user_id) is not None
    keyboard = get_admin_keyboard(has_profile) if is_admin else get_main_keyboard(has_profile)
    await message.answer("Главное меню", reply_markup=keyboard)

@router.message(F.text == "Мой рейтинг")
async def cmd_my_rating(message: Message):
    user_id = message.from_user.id
    rating = await get_user_rating(user_id)
    if rating == 1.0:
        await message.answer("⭐ Ваш текущий рейтинг: **1 ⭐ (начальный)**", parse_mode="Markdown")
    else:
        if rating.is_integer():
            rating_display = f"{int(rating)} ⭐"
        else:
            rating_display = f"{rating:.2f} ⭐"
        await message.answer(f"⭐ Ваш текущий рейтинг: **{rating_display}**", parse_mode="Markdown")

# --------------------- ОБРАБОТКА НЕКОРРЕКТНЫХ СООБЩЕНИЙ ---------------------
@router.message(CreateProfile.waiting_for_name)
async def handle_non_text_name(message: Message):
    await message.answer("Пожалуйста, отправьте текстовое имя.")

@router.message(CreateProfile.waiting_for_age)
async def handle_non_text_age(message: Message):
    await message.answer("Пожалуйста, отправьте возраст числом.")

@router.message(CreateProfile.waiting_for_gender)
async def handle_invalid_gender(message: Message):
    await message.answer("Пожалуйста, выберите пол, используя кнопки.", reply_markup=get_gender_keyboard())

@router.message(CreateProfile.waiting_for_interests)
async def handle_invalid_interests(message: Message):
    await message.answer("Пожалуйста, выберите интересы, используя кнопки.", reply_markup=get_interests_keyboard())

@router.message(CreateProfile.waiting_for_description)
async def handle_non_text_description(message: Message):
    await message.answer("Пожалуйста, отправьте текстовое описание.")

@router.message(CreateProfile.waiting_for_photos)
@router.message(EditProfile.waiting_for_new_photos)
async def handle_non_photo_in_photo_state(message: Message):
    await message.answer("Пожалуйста, отправьте фотографию или нажмите 'Готово'.")

@router.message(EditProfile.choosing_field)
async def handle_invalid_edit_choice(message: Message):
    await message.answer("Пожалуйста, выберите действие из меню ниже.", reply_markup=get_edit_keyboard())

@router.message(EditProfile.waiting_for_new_gender)
async def handle_invalid_new_gender(message: Message):
    await message.answer("Пожалуйста, выберите пол, используя кнопки.", reply_markup=get_gender_keyboard())

@router.message(EditProfile.waiting_for_new_interests)
async def handle_invalid_new_interests(message: Message):
    await message.answer("Пожалуйста, выберите интересы, используя кнопки.", reply_markup=get_interests_keyboard())

@router.message(BrowseProfiles.browsing)
async def handle_in_browsing(message: Message):
    await message.answer("Для возврата в меню используйте кнопку 'Назад в меню'.")