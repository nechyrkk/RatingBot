import random
from data import get_all_profiles, get_ratings, get_profile

async def get_profile_pools(user_id: int):
    """
    Возвращает (new_ids, disliked_ids) для пользователя.
    new_ids – анкеты, которые пользователь ещё не оценивал и которые подходят под его интересы.
    disliked_ids – анкеты, которые пользователь дизлайкнул (подходят под интересы).
    """
    all_profiles = await get_all_profiles()
    current_user = await get_profile(user_id)
    if not current_user:
        return [], []

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
    for uid, profile in all_profiles.items():
        if uid == user_id:
            continue
        if profile.get('gender') not in allowed_genders:
            continue
        if uid in liked:
            continue
        if uid in disliked:
            disliked_ids.append(uid)
        else:
            new_ids.append(uid)

    return new_ids, disliked_ids

async def get_next_profile(user_id: int, state_data: dict) -> (int, dict):
    """
    Возвращает (next_profile_id, updated_state_data) или (None, state_data), если нет анкет.
    state_data должен содержать ключи:
        'new_pool': список ID новых анкет (оставшиеся)
        'disliked_pool': список ID дизлайкнутых анкет (оставшиеся)
        'current_pool': 'new' или 'disliked'
    Если списки пусты, они будут перезаполнены из БД.
    """
    # Если списки не определены или пусты, загружаем из БД
    if 'new_pool' not in state_data or not state_data['new_pool']:
        new_ids, disliked_ids = await get_profile_pools(user_id)
        state_data['new_pool'] = new_ids
        state_data['disliked_pool'] = disliked_ids
        state_data['current_pool'] = 'new'  # начинаем с новых

    # Если в текущем пуле есть элементы
    if state_data['current_pool'] == 'new' and state_data['new_pool']:
        # Берём случайный из новых
        next_id = random.choice(state_data['new_pool'])
        state_data['new_pool'].remove(next_id)
        return next_id, state_data

    # Если новые кончились, переключаемся на дизлайкнутые
    if state_data['current_pool'] == 'new' and not state_data['new_pool']:
        state_data['current_pool'] = 'disliked'

    # Работа с дизлайкнутыми
    if state_data['current_pool'] == 'disliked':
        if state_data['disliked_pool']:
            next_id = random.choice(state_data['disliked_pool'])
            state_data['disliked_pool'].remove(next_id)
            return next_id, state_data
        else:
            # Все дизлайкнутые показаны – сбрасываем пул дизлайков (начинаем цикл заново)
            # Но сначала нужно перезагрузить из БД, чтобы учесть новые дизлайки
            _, disliked_ids = await get_profile_pools(user_id)
            state_data['disliked_pool'] = disliked_ids
            if state_data['disliked_pool']:
                next_id = random.choice(state_data['disliked_pool'])
                state_data['disliked_pool'].remove(next_id)
                return next_id, state_data
            else:
                # Даже дизлайкнутых нет – значит совсем никого
                return None, state_data