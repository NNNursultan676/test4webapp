import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
ADMIN_IDS = {int(i) for i in os.getenv("ADMIN_IDS").split(",")}
COMPANY_LOGO = "🏢"
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "sapabooking")
DB_HOST = os.getenv("POSTGRES_HOST", "postgresql")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")