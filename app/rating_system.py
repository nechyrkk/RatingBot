"""
Модуль для управления системой рейтинга пользователей.
Содержит функции для вычисления веса оценки и получения рейтинга.
"""

import math
import aiosqlite
from data import DB_PATH  # импортируем путь к БД из основного модуля data

async def get_voter_weight(voter_id: int) -> float:
    """
    Возвращает вес голоса пользователя на основе его текущего рейтинга.
    Вес растёт логарифмически, чтобы не было слишком большого разрыва.
    Если рейтинг меньше 1, возвращается вес 1.0.
    """
    rating = await get_user_rating(voter_id)
    # Используем логарифмическую шкалу: ln(1+rating) -> при rating=1 даст ~0.69, но мы можем нормировать
    # Чтобы вес был не меньше 1, добавим смещение: 1 + ln(rating) для rating>0
    # Но проще: вес = 1 + log1p(rating) (логарифм от rating+1)
    weight = 1.0 + math.log1p(rating)  # log1p(x) = ln(1+x)
    return weight

async def get_user_rating(user_id: int) -> float:
    """
    Возвращает текущий рейтинг пользователя.
    Рейтинг вычисляется как средневзвешенное всех полученных оценок.
    Если оценок нет, возвращается 1.0.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT rating_sum, rating_weight FROM profiles WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[1] > 0:
                rating = row[0] / row[1]
                return max(rating, 1.0)  # не ниже 1
            return 1.0  # база

async def add_rating(from_user_id: int, to_user_id: int, value: int, voter_weight: float):
    """
    Сохраняет оценку пользователя from_user_id пользователю to_user_id.
    Обновляет сумму и вес в профиле цели.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Вставляем запись (или обновляем, если уже была)
        await db.execute(
            '''INSERT OR REPLACE INTO ratings 
               (from_user_id, to_user_id, value, voter_weight) 
               VALUES (?, ?, ?, ?)''',
            (from_user_id, to_user_id, value, voter_weight)
        )
        # Обновляем рейтинг цели
        await db.execute(
            '''
            UPDATE profiles 
            SET rating_sum = rating_sum + ? * ?,
                rating_weight = rating_weight + ?
            WHERE user_id = ?
            ''',
            (value, voter_weight, voter_weight, to_user_id)
        )
        await db.commit()