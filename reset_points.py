#!/usr/bin/env python3
import asyncio
import aiosqlite
import os
from pathlib import Path

DB_PATH = Path(__file__).parent / 'app' / 'bot_database.db'

async def reset():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM user_points')
        await db.commit()
    print(f"Очки обнулены в {DB_PATH}")

if __name__ == "__main__":
    asyncio.run(reset())