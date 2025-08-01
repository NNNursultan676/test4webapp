from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database import get_cursor, commit, reset_transaction 

def main_menu_keyboard(is_admin=False, has_bookings=False):
    """Generates the main menu with buttons for members and admins"""
    buttons = [
        [KeyboardButton(text="📅 Забронировать"), KeyboardButton(text="📖 Мои брони")],
        [KeyboardButton(text="📋 Посмотреть брони")]
    ]
    
    # Members can always see and cancel their own bookings if they have any
    #if has_bookings:
    #    buttons.append([KeyboardButton(text="❌ Отменить бронь")])  
    
    # Admins and owner see the "⚙️ Админ" button
    if is_admin:
        buttons.append([KeyboardButton(text="⚙️ Админ")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def generate_date_keyboard(callback_prefix="date"):
    """Создаёт клавиатуру с выбором дат (включая сегодня)"""
    today = datetime.now().date()
    dates = []
    day = today  

    while len(dates) < 7:
        if day.weekday() < 5:  # Исключаем субботу и воскресенье
            dates.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📅 {date}", callback_data=f"{callback_prefix}:{date}")]
        for date in dates
    ])

def generate_hour_keyboard(date: str):
    keyboard = [
        [InlineKeyboardButton(text=f"{hour}:00", callback_data=f"hour_{date}_{hour}")]
        for hour in range(9, 19)  # 09:00 - 18:00
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def generate_minute_keyboard(date: str, hour: str):
    keyboard = [
        [InlineKeyboardButton(text=f"{hour}:{minute:02d}", callback_data=f"minute_{date}_{hour}_{minute}")]
        for minute in range(0, 60, 10)  # Шаг 10 минут
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

#def generate_hour_keyboard(date: str):
#    keyboard = [
#        [InlineKeyboardButton(text=f"{hour}:00", callback_data=f"hour_{date}_{hour}")]
#        for hour in range(9, 19)  # 9:00 to 18:00
#    ]
#    return InlineKeyboardMarkup(inline_keyboard=keyboard)

#def generate_minute_keyboard(date: str, hour: str):
#    keyboard = [
#        [InlineKeyboardButton(text=f"{hour}:{minute:02d}", callback_data=f"minute_{date}_{hour}_{minute}")]
#        for minute in range(0, 60, 10)  # Every 10 minutes
#    ]
#    return InlineKeyboardMarkup(inline_keyboard=keyboard)



def generate_time_keyboard(date):
    reset_transaction()
    """Генерирует клавиатуру с доступными временами на выбранную дату"""
    cursor = get_cursor()
    
    # Получаем забронированные времена на указанную дату
    booked_times = {row[0] for row in cursor.execute(
        "SELECT start_datetime FROM public.bookings WHERE start_datetime LIKE %s", (f"{date}%",)
    ).fetchall()}
    
    # Доступные временные слоты
    times = [f"{hour}:00" for hour in range(9, 18) if f"{date} {hour}:00" not in booked_times]

    # Если все слоты заняты
    if not times:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Нет доступного времени", callback_data="no_slots")]
        ])

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏰ {time}", callback_data=f"time:{date} {time}")]
        for time in times
    ])
def admin_menu_keyboard():
    """Generates the admin menu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить чужую бронь")],
            [KeyboardButton(text="⬅️ Вернуться в главное меню")]
        ],
        resize_keyboard=True
    )
