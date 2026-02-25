# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RatingBot is a Telegram dating/matchmaking bot for university students. It is built with **aiogram 3.x** (async) and **aiosqlite** for async SQLite access. The bot allows users to create profiles, browse others, send likes/superlikes/dislikes, and get matched for in-person meetups.

## Running the Bot

```bash
cd app
python main.py
```

The bot requires a `.env` file in the `app/` directory (or project root) with:
```
BOT_TOKEN=<telegram_bot_token>
ADMIN_IDS=<comma-separated telegram user IDs>
```

## Utility Scripts

```bash
# Reset all monthly points (run from project root)
python reset_points.py
```

## Architecture

The entry point is `app/main.py`, which initializes the DB, creates the Bot and Dispatcher, includes the router from `handlers.py`, and starts polling.

### Module Responsibilities

| File | Role |
|---|---|
| `config.py` | Loads `BOT_TOKEN` and `ADMIN_IDS` from `.env` |
| `data.py` | All DB operations (SQLite via aiosqlite). Also defines `DB_PATH` and `INSTITUTES` list |
| `states.py` | FSM state groups: `CreateProfile`, `EditProfile`, `BrowseProfiles`, `SuperLike` |
| `keyboards.py` | All Reply and Inline keyboard factories |
| `matching.py` | Profile pool logic — filters by gender preference, separates new vs. disliked pools |
| `rating_system.py` | Weighted rating: `get_user_rating`, `add_rating`, `get_voter_weight` (uses `log1p`) |
| `meetings.py` | Meet task lifecycle: propose → agree/decline → video confirmation → admin approval → points |
| `lecture_halls.py` | Static per-institute building/room data (used for meeting location generation) |
| `handlers.py` | Main aiogram Router with all user-facing command and callback handlers; includes `meet_router` |

### Data Flow

1. **Profile creation**: Multi-step FSM (`CreateProfile` states) collects name, age, gender, interests, institute, description, and up to 3 photos.
2. **Browsing**: `BrowseProfiles` state; `matching.get_next_profile()` manages two pools — `new_pool` (unseen) and `disliked_pool` (previously disliked, shown again in a cycle).
3. **Like/Dislike/Superlike**: On mutual like, `meetings.create_meet_after_like()` is triggered if both users share the same institute.
4. **Meet task lifecycle**: `pending` → (both agree) → `waiting_video` → (initiator sends video note) → `waiting_admin` → `confirmed`/`declined`. 10 points awarded per user on confirmation.
5. **Rating system**: After a meetup or superlike interaction, users rate each other 1–5. Voter weight is `log(1 + voter_rating)`. Stored as `rating_sum` / `rating_weight` in `profiles` table.
6. **Points/leaderboard**: Monthly points stored in `user_points(user_id, year_month, points)`. Top users shown via "Топ встреч".

### Database Schema

Six tables in `bot_database.db` (auto-created by `init_db()`):
- `profiles` — user data + `rating_sum`, `rating_weight`, `institute`
- `likes` / `dislikes` — who rated whom
- `ratings` — numeric star ratings with voter weight
- `meet_tasks` — meet proposals with status/confirmation tracking
- `user_points` — monthly points per user

Schema migration is done inline in `init_db()` using `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`.

### Admin Features

Admins (defined in `ADMIN_IDS`) have an extended keyboard with "Статистика" and access to meet confirmation callbacks (`confirm_meet_<id>`, `decline_meet_<id>`). Admin ID list is checked directly against `config.ADMIN_IDS`.

### Key Conventions

- All DB calls use `async with aiosqlite.connect(DB_PATH)` — no persistent connection pool.
- `DB_PATH` is `"bot_database.db"` (relative path), so the bot **must be run from the `app/` directory**.
- Photos are stored as JSON arrays of Telegram `file_id` strings in `profiles.photos`.
- Interests field uses Russian text values: `"Парни"`, `"Девушки"`, `"Все"`.
- Gender field uses: `"Парень"`, `"Девушка"`.
- Institutes: `["ИИТ", "ИИИ", "ИТУ", "ИКБ", "ИТХТ", "ИПТИП"]` (defined in `data.INSTITUTES`).
- Meet proposals are only created when both users share the same institute.
