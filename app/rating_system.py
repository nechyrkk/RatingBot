import math
import aiosqlite
from data import DB_PATH

async def get_user_rating(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT rating_sum, rating_weight FROM profiles WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[1] > 0:
                rating = row[0] / row[1]
                return max(rating, 1.0)
            return 1.0

async def get_voter_weight(voter_id: int) -> float:
    rating = await get_user_rating(voter_id)
    return math.log1p(rating)  # log(1+rating)

async def add_rating(from_user_id: int, to_user_id: int, value: int, voter_weight: float):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT OR IGNORE INTO ratings (from_user_id, to_user_id, value, voter_weight) VALUES (?, ?, ?, ?)',
            (from_user_id, to_user_id, value, voter_weight)
        )
        if cursor.rowcount > 0:
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