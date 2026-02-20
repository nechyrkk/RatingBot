# data.py
import aiosqlite
import json
import math
from typing import Optional, Dict, Any, Set
from aiogram import Bot  # для функции get_all_usernames

DB_PATH = "bot_database.db"

async def init_db():
    """Создаёт таблицы, если их нет, и добавляет поля для рейтинга."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица профилей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                interests TEXT NOT NULL,
                description TEXT NOT NULL,
                photos TEXT NOT NULL
            )
        ''')
        # Добавляем поля для рейтинга, если их ещё нет
        try:
            await db.execute('ALTER TABLE profiles ADD COLUMN rating_sum REAL DEFAULT 0')
        except aiosqlite.OperationalError:
            pass  # поле уже существует
        try:
            await db.execute('ALTER TABLE profiles ADD COLUMN rating_weight REAL DEFAULT 0')
        except aiosqlite.OperationalError:
            pass

        # Таблица лайков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                user_id INTEGER,
                liked_user_id INTEGER,
                PRIMARY KEY (user_id, liked_user_id)
            )
        ''')
        # Таблица дизлайков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS dislikes (
                user_id INTEGER,
                disliked_user_id INTEGER,
                PRIMARY KEY (user_id, disliked_user_id)
            )
        ''')
        # Таблица оценок (рейтинг)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                from_user_id INTEGER,
                to_user_id INTEGER,
                value INTEGER NOT NULL,
                voter_weight REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (from_user_id, to_user_id)
            )
        ''')
        await db.commit()

# ---------- Профили ----------
async def save_profile(user_id: int, name: str, age: int, gender: str, interests: str, description: str, photos: list):
    photos_json = json.dumps(photos)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR REPLACE INTO profiles 
            (user_id, name, age, gender, interests, description, photos, rating_sum, rating_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT rating_sum FROM profiles WHERE user_id=?), 0), 
                    COALESCE((SELECT rating_weight FROM profiles WHERE user_id=?), 0))
        ''', (user_id, name, age, gender, interests, description, photos_json, user_id, user_id))
        await db.commit()

async def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT name, age, gender, interests, description, photos FROM profiles WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                name, age, gender, interests, description, photos_json = row
                photos = json.loads(photos_json)
                return {
                    'name': name,
                    'age': age,
                    'gender': gender,
                    'interests': interests,
                    'description': description,
                    'photos': photos
                }
            return None

async def get_all_profiles() -> Dict[int, Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id, name, age, gender, interests, description, photos FROM profiles'
        ) as cursor:
            rows = await cursor.fetchall()
            profiles = {}
            for row in rows:
                user_id, name, age, gender, interests, description, photos_json = row
                photos = json.loads(photos_json)
                profiles[user_id] = {
                    'name': name,
                    'age': age,
                    'gender': gender,
                    'interests': interests,
                    'description': description,
                    'photos': photos
                }
            return profiles

# ---------- Лайки/дизлайки ----------
async def add_like(user_id: int, target_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO likes (user_id, liked_user_id) VALUES (?, ?)', (user_id, target_id))
        await db.commit()

async def add_dislike(user_id: int, target_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO dislikes (user_id, disliked_user_id) VALUES (?, ?)', (user_id, target_id))
        await db.commit()

async def get_ratings(user_id: int) -> Dict[str, Set[int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        liked = set()
        async with db.execute('SELECT liked_user_id FROM likes WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                liked.add(row[0])
        disliked = set()
        async with db.execute('SELECT disliked_user_id FROM dislikes WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                disliked.add(row[0])
        return {'liked': liked, 'disliked': disliked}

# ---------- Статистика ----------
async def get_user_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT COUNT(*) FROM profiles') as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute('SELECT gender, COUNT(*) FROM profiles GROUP BY gender') as cursor:
            rows = await cursor.fetchall()
            gender_stats = {row[0]: row[1] for row in rows}
        return {'total': total, 'gender': gender_stats}

async def get_all_usernames(bot: Bot) -> dict:
    """
    Возвращает словарь {user_id: отображаемая строка с именем и username}.
    Формат: "Имя (@username)" или "Имя (нет username)" или "Имя (чат недоступен)"
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, name FROM profiles') as cursor:
            rows = await cursor.fetchall()
            result = {}
            for user_id, name in rows:
                try:
                    chat = await bot.get_chat(user_id)
                    if chat.username:
                        display = f"{name} (@{chat.username})"
                    else:
                        display = f"{name} (нет username)"
                except Exception:
                    display = f"{name} (чат недоступен)"
                result[user_id] = display
            return result

# ---------- Удаление ----------
async def delete_profile(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM likes WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM likes WHERE liked_user_id = ?', (user_id,))
        await db.execute('DELETE FROM dislikes WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM dislikes WHERE disliked_user_id = ?', (user_id,))
        await db.execute('DELETE FROM ratings WHERE from_user_id = ? OR to_user_id = ?', (user_id, user_id))
        await db.commit()