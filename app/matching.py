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

async def get_next_profile(user_id: int, state_data: dict):
    """
    Возвращает (next_profile_id, updated_state_data) или (None, state_data), если нет анкет.
    """
    # Если списки не определены или пусты, загружаем из БД
    if 'new_pool' not in state_data or not state_data['new_pool']:
        new_ids, disliked_ids = await get_profile_pools(user_id)
        state_data['new_pool'] = new_ids
        state_data['disliked_pool'] = disliked_ids
        state_data['current_pool'] = 'new'  # начинаем с новых

    # Если в текущем пуле есть элементы
    if state_data['current_pool'] == 'new' and state_data['new_pool']:
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
            # Дизлайкнутые закончились – перезагружаем оба пула и начинаем заново с new
            new_ids, disliked_ids = await get_profile_pools(user_id)
            state_data['new_pool'] = new_ids
            state_data['disliked_pool'] = disliked_ids
            state_data['current_pool'] = 'new'

            # Теперь пробуем взять из обновлённого new_pool
            if state_data['new_pool']:
                next_id = random.choice(state_data['new_pool'])
                state_data['new_pool'].remove(next_id)
                return next_id, state_data
            elif state_data['disliked_pool']:
                # Если новых нет, показываем дизлайкнутые
                state_data['current_pool'] = 'disliked'
                next_id = random.choice(state_data['disliked_pool'])
                state_data['disliked_pool'].remove(next_id)
                return next_id, state_data
            else:
                # Совсем никого нет
                return None, state_data

    # Если дошли сюда – значит что-то не так, но возвращаем None
    return None, state_data