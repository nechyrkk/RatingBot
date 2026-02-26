import random
from data import get_all_profiles, get_ratings, get_profile


async def get_profile_pools(user_id: int):
    """
    Возвращает (new_ids, disliked_ids, liked_ids) для пользователя.
    new_ids     – анкеты, которые пользователь ещё не оценивал.
    disliked_ids – анкеты, которые пользователь дизлайкнул.
    liked_ids   – анкеты, которые пользователь уже лайкнул.
    Все списки отфильтрованы по полу согласно интересам пользователя.
    """
    all_profiles = await get_all_profiles()
    current_user = await get_profile(user_id)
    if not current_user:
        return [], [], []

    interests = current_user['interests']
    allowed_genders = []
    if interests == "Парни":
        allowed_genders = ["Парень"]
    elif interests == "Девушки":
        allowed_genders = ["Девушка"]
    elif interests == "Все":
        allowed_genders = ["Парень", "Девушка"]

    ratings = await get_ratings(user_id)
    liked = ratings['liked']
    disliked = ratings['disliked']

    new_ids = []
    disliked_ids = []
    liked_ids = []
    for uid, profile in all_profiles.items():
        if uid == user_id:
            continue
        if profile.get('gender') not in allowed_genders:
            continue
        if uid in liked:
            liked_ids.append(uid)
        elif uid in disliked:
            disliked_ids.append(uid)
        else:
            new_ids.append(uid)

    return new_ids, disliked_ids, liked_ids


async def get_next_profile(user_id: int, state_data: dict) -> tuple:
    """
    Возвращает (next_profile_id, updated_state_data, is_revisit).
    is_revisit=True означает, что анкета из пула уже лайкнутых (показывается повторно).

    Иерархия фолбэков:
      1. new_pool     — непросмотренные анкеты
      2. disliked_pool — дизлайкнутые (циклично возвращаются в new_pool)
      3. re-fetch DB  — ловит новых зарегистрировавшихся пользователей
      4. liked_pool   — уже лайкнутые анкеты (показывается с пометкой)
    Сценарий «анкет нет» возможен только если пользователь один в системе.
    """
    # Инициализация пулов при первом вызове
    if not state_data.get('pools_loaded'):
        new_ids, disliked_ids, liked_ids = await get_profile_pools(user_id)
        state_data['new_pool'] = new_ids
        state_data['disliked_pool'] = disliked_ids
        state_data['liked_pool'] = liked_ids
        state_data['current_pool'] = 'new'
        state_data['pools_loaded'] = True

    # Фаза 1: новые анкеты
    if state_data['current_pool'] == 'new' and state_data['new_pool']:
        next_id = random.choice(state_data['new_pool'])
        state_data['new_pool'].remove(next_id)
        return next_id, state_data, False

    # new_pool пуст — переходим к дизлайкнутым
    if state_data['current_pool'] == 'new' and not state_data['new_pool']:
        state_data['current_pool'] = 'disliked'

    # Фаза 2: дизлайкнутые анкеты
    if state_data['current_pool'] == 'disliked':
        if state_data['disliked_pool']:
            next_id = random.choice(state_data['disliked_pool'])
            state_data['disliked_pool'].remove(next_id)
            # Возвращаем в new_pool для следующего цикла
            state_data['new_pool'].append(next_id)
            return next_id, state_data, False

        # disliked_pool пуст, но new_pool пополнился (из дизлайков)
        if state_data['new_pool']:
            state_data['current_pool'] = 'new'
            next_id = random.choice(state_data['new_pool'])
            state_data['new_pool'].remove(next_id)
            return next_id, state_data, False

        # Полный цикл завершён — обновляем из БД (ловим новых пользователей)
        new_ids, _, _ = await get_profile_pools(user_id)
        if new_ids:
            state_data['new_pool'] = new_ids
            state_data['current_pool'] = 'new'
            state_data['pools_loaded'] = True
            next_id = random.choice(state_data['new_pool'])
            state_data['new_pool'].remove(next_id)
            return next_id, state_data, False

        # Новых нет — переходим к лайкнутым
        state_data['current_pool'] = 'liked'

    # Фаза 3: уже лайкнутые анкеты (показываются с пометкой)
    if state_data['current_pool'] == 'liked':
        if not state_data.get('liked_pool'):
            # Пополняем из БД
            _, _, liked_ids = await get_profile_pools(user_id)
            state_data['liked_pool'] = liked_ids

        if state_data['liked_pool']:
            next_id = random.choice(state_data['liked_pool'])
            state_data['liked_pool'].remove(next_id)
            return next_id, state_data, True

    # Пользователь один в системе — нет никаких анкет
    return None, state_data, False
