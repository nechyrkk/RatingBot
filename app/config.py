import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")
if not ADMIN_IDS:
    raise ValueError("ADMIN_IDS не задан в .env (укажите хотя бы один ID)")