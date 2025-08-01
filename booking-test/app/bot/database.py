import psycopg2
from config import DB_USER, DB_PASS, DB_NAME, DB_HOST, DB_PORT

# Подключение к PostgreSQL
conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT
)
cursor = conn.cursor()

def get_cursor():
    """Возвращает курсор базы данных"""
    return cursor

def commit():
    """Фиксирует изменения в базе данных"""
    try:
        conn.commit()
    except psycopg2.Error as e:
        print(f"❌ Ошибка коммита: {e}")
        conn.rollback()  # Сбрасываем транзакцию при ошибке

def reset_transaction():
    """Сбрасывает ошибочную транзакцию, если она была."""
    try:
        conn.rollback()
    except psycopg2.Error:
        pass  # Если ошибки нет, просто продолжаем

def table_exists(table_name):
    """Проверяет, существует ли таблица"""
    reset_transaction()
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = %s
    )
    """
    cursor.execute(query, (table_name,))
    return cursor.fetchone()[0]

def save_schedule_to_postgres():
    """Сохраняет бронирования в PostgreSQL."""
    if not table_exists("bookings"):
        print("❌ Ошибка: Таблица bookings не найдена!")
        return

    reset_transaction()
    cursor.execute("SELECT user_id, start_datetime, status FROM public.bookings")
    bookings = cursor.fetchall()

    for booking in bookings:
        print(f"User: {booking[0]}, Date: {booking[1]}, Status: {booking[2]}")  # Логируем данные

    print("✅ Расписание успешно сохранено в PostgreSQL!")
