import aiosqlite
import json
import datetime
from typing import Optional, Dict, Any, Set, Tuple
from aiogram import Bot

DB_PATH = "bot_database.db"

# Список институтов (фиксированный)
INSTITUTES = ["ИИТ", "ИИИ", "ИТУ", "ИКБ", "ИТХТ", "ИПТИП"]

# Эмодзи для разных диапазонов UID
UID_EMOJIS = {
    "1-100": "⭐",      # первые 100 пользователей
    "101-1000": "🌟",    # следующие 900 пользователей
    "1001+": "💫"        # остальные
}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица профилей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                uid INTEGER UNIQUE,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                interests TEXT NOT NULL,
                description TEXT NOT NULL,
                photos TEXT NOT NULL
            )
        ''')
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
        # Таблица заданий на встречу
        await db.execute('''
            CREATE TABLE IF NOT EXISTS meet_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                initiator_id INTEGER NOT NULL,
                institute TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL,
                user1_confirmed INTEGER DEFAULT 0,
                user2_confirmed INTEGER DEFAULT 0,
                msg1_id INTEGER,
                msg2_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline TIMESTAMP,
                video_message_id INTEGER,
                admin_decision INTEGER
            )
        ''')
        # Таблица очков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER NOT NULL,
                year_month TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, year_month)
            )
        ''')
        # Таблица рейтингов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                value INTEGER NOT NULL,
                voter_weight REAL NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(from_user_id, to_user_id)
            )
        ''')

        # === Проверка и добавление новых колонок в существующие таблицы ===

        # Для таблицы profiles
        cursor = await db.execute("PRAGMA table_info(profiles)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'uid' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN uid INTEGER")
            print("Добавлена колонка uid в profiles")
        
        if 'institute' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN institute TEXT DEFAULT 'ИИТ'")
            print("Добавлена колонка institute в profiles")
        
        if 'rating_sum' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN rating_sum REAL DEFAULT 0")
            print("Добавлена колонка rating_sum в profiles")
        
        if 'rating_weight' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN rating_weight REAL DEFAULT 0")
            print("Добавлена колонка rating_weight в profiles")

        # Для таблицы meet_tasks
        cursor = await db.execute("PRAGMA table_info(meet_tasks)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'user1_confirmed' not in column_names:
            await db.execute("ALTER TABLE meet_tasks ADD COLUMN user1_confirmed INTEGER DEFAULT 0")
            print("Добавлена колонка user1_confirmed в meet_tasks")
        if 'user2_confirmed' not in column_names:
            await db.execute("ALTER TABLE meet_tasks ADD COLUMN user2_confirmed INTEGER DEFAULT 0")
            print("Добавлена колонка user2_confirmed в meet_tasks")
        if 'msg1_id' not in column_names:
            await db.execute("ALTER TABLE meet_tasks ADD COLUMN msg1_id INTEGER")
            print("Добавлена колонка msg1_id в meet_tasks")
        if 'msg2_id' not in column_names:
            await db.execute("ALTER TABLE meet_tasks ADD COLUMN msg2_id INTEGER")
            print("Добавлена колонка msg2_id в meet_tasks")

        await db.commit()

async def get_next_uid() -> int:
    """Генерирует следующий доступный UID"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT MAX(uid) FROM profiles') as cursor:
            row = await cursor.fetchone()
            return (row[0] or 0) + 1

async def assign_uids_to_existing_users():
    """Присваивает UID всем существующим пользователям в порядке создания"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей без uid, отсортированных по rowid (порядок создания)
        async with db.execute('''
            SELECT user_id FROM profiles 
            WHERE uid IS NULL 
            ORDER BY rowid
        ''') as cursor:
            users = await cursor.fetchall()
        
        if not users:
            return
        
        # Получаем максимальный текущий uid
        async with db.execute('SELECT MAX(uid) FROM profiles') as cursor:
            row = await cursor.fetchone()
            current_max = row[0] or 0
        
        # Присваиваем uid по порядку
        for i, (user_id,) in enumerate(users, start=1):
            new_uid = current_max + i
            await db.execute(
                'UPDATE profiles SET uid = ? WHERE user_id = ?',
                (new_uid, user_id)
            )
        
        await db.commit()
        print(f"Присвоены UID {len(users)} пользователям")

# ---------- Профили ----------
async def save_profile(user_id: int, name: str, age: int, gender: str, interests: str, 
                      institute: str, description: str, photos: list, uid: int = None):
    photos_json = json.dumps(photos)
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем текущие значения рейтинга и uid, если профиль уже существует
        async with db.execute('''
            SELECT rating_sum, rating_weight, uid FROM profiles WHERE user_id = ?
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
        
        if row:
            rating_sum, rating_weight, existing_uid = row
            # Если uid не передан, используем существующий
            final_uid = uid if uid is not None else existing_uid
        else:
            rating_sum, rating_weight = 0.0, 0.0
            # Для нового профиля генерируем uid
            final_uid = uid if uid is not None else await get_next_uid()
        
        await db.execute('''
            INSERT OR REPLACE INTO profiles
            (user_id, uid, name, age, gender, interests, institute, description, photos, rating_sum, rating_weight)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, final_uid, name, age, gender, interests, institute, description, photos_json, rating_sum, rating_weight))
        await db.commit()

async def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT uid, name, age, gender, interests, institute, description, photos 
            FROM profiles WHERE user_id = ?
        ''', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                uid, name, age, gender, interests, institute, description, photos_json = row
                photos = json.loads(photos_json)
                return {
                    'uid': uid,
                    'name': name,
                    'age': age,
                    'gender': gender,
                    'interests': interests,
                    'institute': institute,
                    'description': description,
                    'photos': photos
                }
            return None

async def get_all_profiles() -> Dict[int, Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('''
            SELECT user_id, uid, name, age, gender, interests, institute, description, photos 
            FROM profiles
        ''') as cursor:
            rows = await cursor.fetchall()
            profiles = {}
            for row in rows:
                user_id, uid, name, age, gender, interests, institute, description, photos_json = row
                photos = json.loads(photos_json)
                profiles[user_id] = {
                    'uid': uid,
                    'name': name,
                    'age': age,
                    'gender': gender,
                    'interests': interests,
                    'institute': institute,
                    'description': description,
                    'photos': photos
                }
            return profiles

async def update_profile_institute(user_id: int, institute: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE profiles SET institute = ? WHERE user_id = ?', (institute, user_id))
        await db.commit()

def get_uid_emoji(uid: int) -> str:
    """Возвращает эмодзи на основе UID"""
    if uid <= 100:
        return UID_EMOJIS["1-100"]
    elif uid <= 1000:
        return UID_EMOJIS["101-1000"]
    else:
        return UID_EMOJIS["1001+"]

# ---------- Оценки (лайки/дизлайки) ----------
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
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, uid, name FROM profiles') as cursor:
            rows = await cursor.fetchall()
            result = {}
            for user_id, uid, name in rows:
                try:
                    chat = await bot.get_chat(user_id)
                    emoji = get_uid_emoji(uid) if uid else ""
                    if chat.username:
                        display = f"{emoji} {name} (@{chat.username})"
                    else:
                        display = f"{emoji} {name} (нет username)"
                except Exception:
                    display = f"{emoji} {name} (чат недоступен)"
                result[user_id] = display
            return result

# ---------- Задания на встречу (meet_tasks) ----------
async def create_meet_task(user1_id: int, user2_id: int, initiator_id: int, institute: str, location: str, deadline: datetime.datetime, msg1_id: int = None, msg2_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'INSERT INTO meet_tasks (user1_id, user2_id, initiator_id, institute, location, status, deadline, user1_confirmed, user2_confirmed, msg1_id, msg2_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (user1_id, user2_id, initiator_id, institute, location, 'pending', deadline, 0, 0, msg1_id, msg2_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_meet_task_by_id(task_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM meet_tasks WHERE id = ?', (task_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

async def get_active_meet_task_for_user(user_id: int, status: str = 'waiting_video'):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT * FROM meet_tasks WHERE (user1_id = ? OR user2_id = ?) AND status = ? AND deadline > CURRENT_TIMESTAMP',
            (user_id, user_id, status)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

async def update_meet_task_status(task_id: int, status: str, video_message_id: int = None, admin_decision: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        query = 'UPDATE meet_tasks SET status = ?'
        params = [status]
        if video_message_id is not None:
            query += ', video_message_id = ?'
            params.append(video_message_id)
        if admin_decision is not None:
            query += ', admin_decision = ?'
            params.append(admin_decision)
        query += ' WHERE id = ?'
        params.append(task_id)
        await db.execute(query, params)
        await db.commit()

async def update_meet_agreement(task_id: int, user_id: int, agreed: bool):
    """Обновляет статус согласия пользователя в задании.
       Возвращает:
         - 'both_agreed', если оба согласились
         - 'agreed', если только этот пользователь согласился
         - 'declined', если пользователь отказался (статус задания меняется на declined)
         - None, если задание не найдено или уже не в статусе pending
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем задание
        async with db.execute('SELECT user1_id, user2_id, status FROM meet_tasks WHERE id = ?', (task_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            user1, user2, status = row

        if status != 'pending':
            return None  # уже обработано

        if user_id == user1:
            column = 'user1_confirmed'
            other_id = user2
        elif user_id == user2:
            column = 'user2_confirmed'
            other_id = user1
        else:
            return None

        if agreed:
            # Отмечаем согласие
            await db.execute(f'UPDATE meet_tasks SET {column} = 1 WHERE id = ?', (task_id,))
            # Проверяем, оба ли согласны
            async with db.execute('SELECT user1_confirmed, user2_confirmed FROM meet_tasks WHERE id = ?', (task_id,)) as cursor:
                row = await cursor.fetchone()
                if row and row[0] == 1 and row[1] == 1:
                    # Оба согласны -> переводим в waiting_video
                    await db.execute('UPDATE meet_tasks SET status = ? WHERE id = ?', ('waiting_video', task_id))
                    await db.commit()
                    return 'both_agreed'
            await db.commit()
            return 'agreed'
        else:
            # Отказ -> меняем статус на declined
            await db.execute('UPDATE meet_tasks SET status = ? WHERE id = ?', ('declined', task_id))
            await db.commit()
            return 'declined'

# ---------- Очки ----------
async def add_points(user_id: int, points: int):
    year_month = datetime.datetime.now().strftime('%Y-%m')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO user_points (user_id, year_month, points) VALUES (?, ?, ?)
            ON CONFLICT(user_id, year_month) DO UPDATE SET points = points + ?
        ''', (user_id, year_month, points, points))
        await db.commit()

async def get_top_users(limit: int = 10):
    year_month = datetime.datetime.now().strftime('%Y-%m')
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id, points FROM user_points WHERE year_month = ? ORDER BY points DESC LIMIT ?',
            (year_month, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

async def reset_all_points():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM user_points')
        await db.commit()

# ---------- Удаление профиля ----------
async def delete_profile(user_id: int):
    """Полностью удаляет профиль пользователя и все связанные записи."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Удаляем из таблиц likes, dislikes, ratings, meet_tasks, user_points, profiles
        await db.execute('DELETE FROM likes WHERE user_id = ? OR liked_user_id = ?', (user_id, user_id))
        await db.execute('DELETE FROM dislikes WHERE user_id = ? OR disliked_user_id = ?', (user_id, user_id))
        await db.execute('DELETE FROM ratings WHERE from_user_id = ? OR to_user_id = ?', (user_id, user_id))
        await db.execute('DELETE FROM meet_tasks WHERE user1_id = ? OR user2_id = ? OR initiator_id = ?', (user_id, user_id, user_id))
        await db.execute('DELETE FROM user_points WHERE user_id = ?', (user_id,))
        await db.execute('DELETE FROM profiles WHERE user_id = ?', (user_id,))
        await db.commit()