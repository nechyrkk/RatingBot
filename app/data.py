import aiosqlite
import json
import datetime
import random
from typing import Optional, Dict, Any, Set, Tuple, List
from aiogram import Bot

DB_PATH = "bot_database.db"

# Список институтов (фиксированный)
INSTITUTES = ["ИИТ", "ИИИ", "ИТУ", "ИКБ", "ИТХТ", "ИПТИП"]

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица профилей (создаётся без новых колонок, они будут добавлены позже)
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
        # Таблица лайков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                user_id INTEGER,
                liked_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
        # Таблица заданий на встречу (с новыми колонками)
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

        # Таблица стриков
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_streaks (
                user_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_active_date TEXT
            )
        ''')
        # Таблица бейджей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id INTEGER,
                badge_type TEXT,
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, badge_type)
            )
        ''')
        # Таблица ежедневных заданий
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_task_completions (
                user_id INTEGER,
                task_date TEXT,
                task_type TEXT,
                PRIMARY KEY (user_id, task_date, task_type)
            )
        ''')
        # Таблица кулдауна рулетки
        await db.execute('''
            CREATE TABLE IF NOT EXISTS roulette_cooldowns (
                user_id INTEGER PRIMARY KEY,
                last_date TEXT
            )
        ''')
        # Таблица просмотров профилей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS profile_views (
                viewer_id INTEGER,
                viewed_id INTEGER,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (viewer_id, viewed_id)
            )
        ''')

        # Новые колонки в profiles
        cursor = await db.execute("PRAGMA table_info(profiles)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'verified' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN verified INTEGER DEFAULT 0")
            print("Добавлена колонка verified в profiles")
        if 'video_file_id' not in column_names:
            await db.execute("ALTER TABLE profiles ADD COLUMN video_file_id TEXT")
            print("Добавлена колонка video_file_id в profiles")

        # created_at в likes
        cursor = await db.execute("PRAGMA table_info(likes)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'created_at' not in column_names:
            await db.execute("ALTER TABLE likes ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("Добавлена колонка created_at в likes")

        await db.commit()

# ---------- Профили ----------
async def save_profile(user_id: int, name: str, age: int, gender: str, interests: str, institute: str, description: str, photos: list):
    photos_json = json.dumps(photos)
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем текущие значения рейтинга и новых колонок, если профиль уже существует
        async with db.execute('SELECT rating_sum, rating_weight, verified, video_file_id FROM profiles WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            rating_sum, rating_weight, verified, video_file_id = row
        else:
            rating_sum, rating_weight, verified, video_file_id = 0.0, 0.0, 0, None

        await db.execute('''
            INSERT OR REPLACE INTO profiles
            (user_id, name, age, gender, interests, institute, description, photos, rating_sum, rating_weight, verified, video_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, age, gender, interests, institute, description, photos_json, rating_sum, rating_weight, verified, video_file_id))
        await db.commit()

async def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT name, age, gender, interests, institute, description, photos, verified, video_file_id FROM profiles WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                name, age, gender, interests, institute, description, photos_json, verified, video_file_id = row
                try:
                    photos = json.loads(photos_json)
                except (json.JSONDecodeError, TypeError):
                    photos = []
                return {
                    'name': name,
                    'age': age,
                    'gender': gender,
                    'interests': interests,
                    'institute': institute,
                    'description': description,
                    'photos': photos,
                    'verified': verified or 0,
                    'video_file_id': video_file_id,
                }
            return None

async def get_all_profiles() -> Dict[int, Dict[str, Any]]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT user_id, name, age, gender, interests, institute, description, photos FROM profiles') as cursor:
            rows = await cursor.fetchall()
            profiles = {}
            for row in rows:
                user_id, name, age, gender, interests, institute, description, photos_json = row
                try:
                    photos = json.loads(photos_json)
                except (json.JSONDecodeError, TypeError):
                    photos = []
                profiles[user_id] = {
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

# ---------- Горячие сегодня (фича 1) ----------
async def get_hot_profiles(limit: int = 3) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT liked_user_id, COUNT(*) as cnt FROM likes "
            "WHERE created_at >= datetime('now', '-24 hours') "
            "GROUP BY liked_user_id ORDER BY cnt DESC LIMIT ?",
            (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# ---------- Стрики (фича 2) ----------
async def update_streak(user_id: int) -> dict:
    """Обновляет стрик пользователя. Возвращает {current, milestone}."""
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT current_streak, longest_streak, last_active_date FROM user_streaks WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            current, longest, last_date = row
            if last_date == today:
                return {'current': current, 'milestone': None}
            elif last_date == yesterday:
                current += 1
            else:
                current = 1
            longest = max(longest, current)
            await db.execute(
                'UPDATE user_streaks SET current_streak = ?, longest_streak = ?, last_active_date = ? WHERE user_id = ?',
                (current, longest, today, user_id)
            )
        else:
            current, longest = 1, 1
            await db.execute(
                'INSERT INTO user_streaks (user_id, current_streak, longest_streak, last_active_date) VALUES (?, ?, ?, ?)',
                (user_id, current, longest, today)
            )
        await db.commit()

    milestone = None
    if current in (7, 30):
        milestone = current
    return {'current': current, 'milestone': milestone}

async def get_streak(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT current_streak FROM user_streaks WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ---------- Счётчик входящих лайков (фича 4) ----------
async def count_pending_likes(user_id: int) -> int:
    """Количество пользователей, лайкнувших user_id, которым user_id ещё не ответил лайком."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM likes WHERE liked_user_id = ? '
            'AND user_id NOT IN (SELECT liked_user_id FROM likes WHERE user_id = ?)',
            (user_id, user_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ---------- Топ института (фича 5) ----------
async def get_top_users_by_institute(institute: str, limit: int = 10) -> List[tuple]:
    year_month = datetime.datetime.now().strftime('%Y-%m')
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT p.user_id, p.name, up.points FROM profiles p '
            'JOIN user_points up ON p.user_id = up.user_id '
            'WHERE p.institute = ? AND up.year_month = ? '
            'ORDER BY up.points DESC LIMIT ?',
            (institute, year_month, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2]) for row in rows]

# ---------- Бейджи (фича 6) ----------
async def award_badge(user_id: int, badge_type: str) -> bool:
    """Выдаёт бейдж. Возвращает True если бейдж новый."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT 1 FROM user_badges WHERE user_id = ? AND badge_type = ?', (user_id, badge_type)) as cursor:
            exists = await cursor.fetchone()
        if exists:
            return False
        await db.execute('INSERT INTO user_badges (user_id, badge_type) VALUES (?, ?)', (user_id, badge_type))
        await db.commit()
        return True

async def get_user_badges(user_id: int) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT badge_type FROM user_badges WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

# ---------- Ежедневные задания (фича 7) ----------
async def get_daily_task_completions(user_id: int) -> List[str]:
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT task_type FROM daily_task_completions WHERE user_id = ? AND task_date = ?',
            (user_id, today)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def complete_daily_task(user_id: int, task_type: str) -> bool:
    """Отмечает задание выполненным. Возвращает True если впервые сегодня."""
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT 1 FROM daily_task_completions WHERE user_id = ? AND task_date = ? AND task_type = ?',
            (user_id, today, task_type)
        ) as cursor:
            exists = await cursor.fetchone()
        if exists:
            return False
        await db.execute(
            'INSERT INTO daily_task_completions (user_id, task_date, task_type) VALUES (?, ?, ?)',
            (user_id, today, task_type)
        )
        await db.commit()
        return True

async def count_today_likes(user_id: int) -> int:
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM likes WHERE user_id = ? AND date(created_at) = ?",
            (user_id, today)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# ---------- Сезонные события (фича 8) ----------
def get_seasonal_info() -> dict:
    """Возвращает {name, multiplier} для текущей даты."""
    today = datetime.date.today()
    if today.month == 2 and today.day == 14:
        return {'name': 'День святого Валентина', 'multiplier': 2.0}
    if today.month == 9 and today.day == 1:
        return {'name': 'День знаний', 'multiplier': 1.5}
    return {'name': None, 'multiplier': 1.0}

# ---------- Рулетка (фича 9) ----------
async def can_use_roulette(user_id: int) -> bool:
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT last_date FROM roulette_cooldowns WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == today:
                return False
            return True

async def set_roulette_used(user_id: int):
    today = datetime.date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR REPLACE INTO roulette_cooldowns (user_id, last_date) VALUES (?, ?)',
            (user_id, today)
        )
        await db.commit()

async def get_random_profile_other_institute(user_id: int, own_institute: str) -> Optional[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT user_id FROM profiles WHERE institute != ? AND user_id != ?',
            (own_institute, user_id)
        ) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                return None
            return random.choice(rows)[0]

# ---------- Верификация (фича 10) ----------
async def set_verified(user_id: int, verified: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE profiles SET verified = ? WHERE user_id = ?', (verified, user_id))
        await db.commit()

# ---------- Кто смотрел (фича 12) ----------
async def record_profile_view(viewer_id: int, viewed_id: int):
    if viewer_id == viewed_id:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT OR REPLACE INTO profile_views (viewer_id, viewed_id, viewed_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
            (viewer_id, viewed_id)
        )
        await db.commit()

async def get_recent_viewers(user_id: int, limit: int = 5) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT pv.viewer_id, p.name, pv.viewed_at FROM profile_views pv '
            'JOIN profiles p ON pv.viewer_id = p.user_id '
            'WHERE pv.viewed_id = ? ORDER BY pv.viewed_at DESC LIMIT ?',
            (user_id, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{'user_id': row[0], 'name': row[1], 'viewed_at': row[2]} for row in rows]

# ---------- Видео в анкете (фича 13) ----------
async def save_profile_video(user_id: int, video_file_id: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE profiles SET video_file_id = ? WHERE user_id = ?', (video_file_id, user_id))
        await db.commit()