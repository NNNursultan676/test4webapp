from aiogram import types,Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from keyboards import main_menu_keyboard, admin_menu_keyboard, generate_date_keyboard, generate_time_keyboard, generate_hour_keyboard, generate_minute_keyboard
from utils import get_user_role
from database import get_cursor, commit, reset_transaction 



class BookingState(StatesGroup):
    awaiting_name = State()
    awaiting_company = State()

async def check_membership(user_id: int, message: Message) -> bool:
    """Проверяет, является ли пользователь участником группы"""
    # Get the user's role (admin, owner, member)
    role = await get_user_role(message.bot, user_id)

    # Allow all roles (member, admin, owner) to interact with the bot
    if role == "unknown":
        await message.answer("❌ Не удалось проверить участие в группе. Пожалуйста, убедитесь, что бот является администратором и имеет доступ к информации о пользователях.")
        return False
    if role in {"member", "admin", "owner"}:
        return True

    await message.answer("❌ Вы должны быть участником группы, чтобы использовать бота.")
    return False

async def show_main_menu(message: Message, name: str, bot):
    """Отображает главное меню"""
    if not await check_membership(message.from_user.id, message):
        return
    role = await get_user_role(bot, message.from_user.id)
    is_admin = role in {"admin", "owner"}
    reset_transaction()
    cursor = get_cursor()
    cursor.execute("SELECT start_datetime FROM public.bookings WHERE user_id = %s", (message.from_user.id,))
    bookings = cursor.fetchall()

    has_bookings = len(bookings) > 0

    await message.answer(f"🎉 {name}, добро пожаловать в систему бронирования!", reply_markup=main_menu_keyboard(is_admin, has_bookings))

async def start_command(message: Message, state: FSMContext, bot):
    """Запускает бота и проверяет, есть ли у пользователя данные"""
    user_id = message.from_user.id
    if not await check_membership(user_id, message):
        return
    reset_transaction()
    cursor = get_cursor()
    cursor.execute("SELECT first_name, company FROM public.users WHERE tg_id = %s", (user_id,))
    user = cursor.fetchone()

    if not user or not user[0]:
        await message.answer("👋 Привет! Введите ваше имя:")
        await state.set_state(BookingState.awaiting_name)
    elif not user[1]:
        await message.answer("✅ Имя уже есть! Теперь введите название вашей компании:")
        await state.set_state(BookingState.awaiting_company)
    else:
        await show_main_menu(message, user[0], bot)

async def ask_name(message: Message, state: FSMContext):
    """Запрашивает имя пользователя и сохраняет его"""
    user_id = message.from_user.id
    if not await check_membership(user_id, message):
        return

    first_name = message.text.strip()
    if len(first_name) < 2:
        await message.answer("❌ Имя должно содержать хотя бы 2 символа. Попробуйте ещё раз.")
        return
    reset_transaction()
    cursor = get_cursor()
    cursor.execute("INSERT INTO users (tg_id, first_name) VALUES (%s, %s) ON CONFLICT(tg_id) DO UPDATE SET first_name = excluded.first_name;", (user_id, first_name))
    commit()

    await message.answer("✅ Имя сохранено! Теперь введите название вашей компании:")
    await state.set_state(BookingState.awaiting_company)

async def ask_company(message: Message, state: FSMContext):
    """Сохраняет компанию пользователя и показывает главное меню"""
    user_id = message.from_user.id
    if not await check_membership(user_id, message):
        return

    company = message.text.strip()
    if len(company) < 2:
        await message.answer("❌ Название компании слишком короткое. Попробуйте ещё раз.")
        return
    reset_transaction()
    cursor = get_cursor()
    cursor.execute("UPDATE users SET company = %s WHERE tg_id = %s", (company, user_id))
    commit()

    cursor.execute("SELECT first_name FROM public.users WHERE tg_id = %s", (user_id,))
    first_name = cursor.fetchone()
    
    if first_name:
        await state.clear()
        await show_main_menu(message, first_name[0], bot=message.bot)
    else:
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте снова.")



async def book_appointment(message: Message):
    """Открывает календарь с выбором даты"""
    if not await check_membership(message.from_user.id, message):
        return
    await message.answer("📅 Выберите дату:", reply_markup=generate_date_keyboard("date"))


async def select_date(callback: CallbackQuery):
    """После выбора даты предлагает выбрать время"""
    if not await check_membership(callback.from_user.id, callback.message):
        return
    date = callback.data.split(":")[1]
    await callback.message.edit_text(f"📅 Выберите время для {date}:", reply_markup=generate_hour_keyboard(date))



#def generate_hour_keyboard(date):
#    """Генерирует клавиатуру для выбора времени"""
#    keyboard = [
#        [InlineKeyboardButton(text=f"🕒 {hour}:00", callback_data=f"time:{date} {hour}:00")]
#        for hour in range(9, 18)  # Рабочие часы с 9:00 до 17:00
#    ]
#    return InlineKeyboardMarkup(inline_keyboard=keyboard)
#
#def generate_minute_keyboard(date, hour):
#    """Генерация клавиатуры выбора минут"""
#    keyboard = InlineKeyboardMarkup(row_width=3)
#    for minute in range(0, 60, 10):
#        keyboard.insert(InlineKeyboardButton(text=f"{hour}:{minute:02d}", callback_data=f"minute_{date}_{hour}_{minute}"))
#    return keyboard
#
#
async def process_hour_selection(callback_query: CallbackQuery):
    """Обработчик выбора часа"""
    parts = callback_query.data.split("_")
    if len(parts) != 3:
        return await callback_query.answer("Ошибка обработки данных!")

    _, date, hour = parts

    await callback_query.message.edit_text(
        f"⏳ Выберите минуты для {date} {hour}:00:",
        reply_markup=generate_minute_keyboard(date, hour)
    )

async def process_minute_selection(callback_query: CallbackQuery):
    """Обработчик выбора минут и подтверждение бронирования"""
    parts = callback_query.data.split("_")
    if len(parts) != 4:
        return await callback_query.answer("Ошибка обработки данных!")

    _, date, hour, minute = parts
    start_time = f"{date} {hour}:{minute}"
    end_time = f"{date} {int(hour) + 1}:{minute}"

    try:
        reset_transaction()
        cursor = get_cursor()
        cursor.execute("INSERT INTO public.bookings (user_id, start_datetime, end_datetime, status) VALUES (%s, %s, %s, %s)",
               (callback_query.from_user.id, start_time, end_time, 'active'))  # Или другой статус по умолчанию
        commit()

        await callback_query.message.edit_text(
            f"✅ Бронь с {hour}:{minute} до {int(hour) + 1}:{minute} создана! 🎉"
        )
    except Exception as e:
        await callback_query.answer(f"Ошибка бронирования: {str(e)}")

#async def process_hour_selection(callback_query: CallbackQuery):
#    """Обработчик выбора часа"""
#    parts = callback_query.data.split("_")
#    if len(parts) != 3:
#        return await callback_query.answer("Ошибка обработки данных!")
#
#    _, date, hour = parts
#
#    await callback_query.message.edit_text(
#        f"⏳ Выберите минуты для {date} {hour}:00:",
#        reply_markup=generate_minute_keyboard(date, hour)
#    )
#
#async def process_minute_selection(callback_query: CallbackQuery):
#    """Обработчик выбора минут и подтверждение бронирования"""
#    parts = callback_query.data.split("_")
#    if len(parts) != 4:
#        return await callback_query.answer("Ошибка обработки данных!")
#
#    _, date, hour, minute = parts
#    start_time = f"{date} {hour}:{minute}:00"
#    end_time = f"{date} {int(hour) + 1}:{minute}:00"
#
#    try:
#        reset_transaction()
#        cursor = get_cursor()
#        cursor.execute("INSERT INTO public.bookings (user_id, start_datetime, end_datetime, status) VALUES (%s, %s, %s, %s)",
#               (callback_query.from_user.id, start_time, end_time, 'active'))  # Или другой статус по умолчанию
#        commit()
#        await callback_query.message.edit_text(
#            f"✅ Бронь с {hour}:{minute} до {int(hour) + 1}:{minute} создана! 🎉"
#        )
#
#
#        #await callback_query.message.edit_text(
#        #    f"✅ Бронь с {hour}:{minute} до {int(hour) + 1}:{minute} создана! 🎉"
#        #)
#    except Exception as e:
#        await callback_query.answer(f"Ошибка бронирования: {str(e)}")
#
##async def book_appointment(message: Message):
#    """Открывает календарь с выбором даты"""
#    if not await check_membership(message.from_user.id, message):
#        return
#    await message.answer("📅 Выберите дату:", reply_markup=generate_date_keyboard("date"))
#
#async def select_date(callback: CallbackQuery):
#    """После выбора даты предлагает выбрать время"""
#    if not await check_membership(callback.from_user.id, callback.message):
#        return
#    date = callback.data.split(":")[1]
#    await callback.message.edit_text(f"📅 Выберите время для {date}:", reply_markup=generate_time_keyboard(date))
#
#async def select_time(callback: CallbackQuery):
#    """Сохраняет выбранное время бронирования"""
#    if not await check_membership(callback.from_user.id, callback.message):
#        return
#    reset_transaction()
#    cursor = get_cursor()
#    user_id = callback.from_user.id
#    booking_time = callback.data.split(":", 1)[1]
#
#    cursor.execute("INSERT INTO bookings (user_id, start_datetime) VALUES (%s, %s)", (user_id, booking_time))
#    commit()
#
#    await callback.message.edit_text(f"✅ Бронь подтверждена на {booking_time}! 🎉")

async def my_bookings(message: Message):
    """Shows the user's bookings with cancel options"""
    if not await check_membership(message.from_user.id, message):
        return
    reset_transaction()
    cursor = get_cursor()
    user_id = message.from_user.id
    cursor.execute("SELECT user_id, start_datetime FROM public.bookings WHERE user_id = %s", (user_id,))
    bookings = cursor.fetchall()

    if bookings:
        text = "📌 Ваши брони:\n" + "\n".join([f"🕒 {row[1].strftime('%H:%M')}" for row in bookings])
        #text = "📌 Ваши брони:\n" + "\n".join([f"🕒 {row[1]}" for row in bookings])
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ Отменить {row[1]}", callback_data=f"cancel:{row[0]}")]  # Pass the booking ID here
            for row in bookings
        ])
    else:
        text = "❌ У вас нет активных бронирований."
        keyboard = None  # No buttons if no bookings

    await message.answer(text, reply_markup=keyboard)

async def view_bookings(message: Message):
    """Показывает клавиатуру с выбором даты"""
    if not await check_membership(message.from_user.id, message):
        return

    await message.answer("📅 Выберите дату для просмотра броней:", reply_markup=generate_date_keyboard("view_broni"))

async def show_bookings_for_date(callback: CallbackQuery):
    """Отображает список броней на выбранную дату"""
    if not await check_membership(callback.from_user.id, callback.message):
        return

    selected_date = callback.data.split(":")[1]
    reset_transaction()
    cursor = get_cursor()
    cursor.execute("""
    SELECT b.start_datetime, u.first_name, u.company 
    FROM public.bookings b 
    JOIN public.users u ON b.user_id = u.tg_id 
    WHERE b.start_datetime::TEXT LIKE %s
    """, (f"{selected_date}%",))

    bookings = cursor.fetchall()

    if bookings:
        text = "📌 Ваши брони:\n" + "\n".join([f"🕒 {row[1].strftime('%H:%M')}" for row in bookings])
        #text = f"📌 Брони на {selected_date}:\n" + "\n".join([f"🕒 {start} - 👤 {name} ({company})" for start, name, company in bookings])
    else:
        text = f"❌ На {selected_date} нет заявок."

    await callback.message.edit_text(text)

async def cancel_booking(message: Message):
    """Отображает список броней с возможностью отмены"""
    if not await check_membership(message.from_user.id, message):
        return
    reset_transaction()
    cursor = get_cursor()
    user_id = message.from_user.id
    cursor.execute("SELECT user_id, start_datetime FROM public.bookings WHERE user_id = %s", (user_id,))
    bookings = cursor.fetchall()

    if not bookings:
        await message.answer("❌ У вас нет активных заявок.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"❌ Отменить {row[1]}", callback_data=f"cancel:{row[0]}")]
        for row in bookings
    ])

    await message.answer("Выберите бронь для отмены:", reply_markup=keyboard)

async def confirm_cancel(callback: CallbackQuery):
    """Удаляет бронь после подтверждения"""
    if not await check_membership(callback.from_user.id, callback.message):
        return
    reset_transaction()
    booking_id = callback.data.split(":")[1]
    cursor = get_cursor()

    cursor.execute("DELETE FROM public.bookings WHERE user_id = %s", (booking_id,))
    commit()

    await callback.message.edit_text("✅ Бронь успешно отменена!")

async def show_admin_menu(message: Message):
    """Отображает меню администратора или сообщает об отсутствии прав"""
    # Check if the user is an admin or the owner
    role = await get_user_role(message.bot, message.from_user.id)
    
    # If the user is an admin or owner, show the admin menu
    if role in ["admin", "owner"]:
        await message.answer("⚙️ Админ меню:", reply_markup=admin_menu_keyboard())
    else:
        # Provide more detailed feedback for users without admin rights
        if role == "member":
            await message.answer("❌ У вас нет прав для доступа к админ меню. Вы обычный участник группы.")
        else:
            await message.answer("❌ У вас нет прав для доступа к админ меню. Пожалуйста, обратитесь к администратору.")



async def handle_admin_action(message: Message):
    """Обрабатывает действия админа"""
    if message.text == "❌ Отменить чужую бронь":
        reset_transaction()
        cursor = get_cursor()
        cursor.execute("SELECT start_datetime, user_id FROM public.bookings")
        bookings = cursor.fetchall()

        if not bookings:
            await message.answer("❌ Нет активных броней для отмены.")
            return

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ Отменить {row[1]}", callback_data=f"cancel:{row[0]}")]
            for row in bookings
        ])
        
        await message.answer("Выберите бронь для отмены:", reply_markup=keyboard)
    
    elif message.text == "⬅️ Вернуться в главное меню":
        await show_main_menu(message, message.from_user.first_name, message.bot)

async def handle_admin_button_click(message: Message):
    """Обрабатывает нажатие кнопки ⚙️ Админ"""
    if message.text == "⚙️ Админ":
        await show_admin_menu(message)


def register_handlers(dp: Dispatcher):
    dp.message.register(start_command, Command("start"))
    dp.message.register(ask_name, BookingState.awaiting_name)
    dp.message.register(ask_company, BookingState.awaiting_company)
    dp.message.register(book_appointment, lambda message: message.text == "📅 Забронировать")
    dp.callback_query.register(select_date, lambda callback: callback.data.startswith("date:"))
    dp.callback_query.register(process_hour_selection, lambda callback: callback.data.startswith("hour_"))
    dp.callback_query.register(process_minute_selection, lambda callback: callback.data.startswith("minute_"))
    #dp.message.register(book_appointment, lambda message: message.text == "📅 Забронировать")
    #dp.callback_query.register(select_date, lambda callback: callback.data.startswith("date:"))
    #dp.callback_query.register(select_time, lambda callback: callback.data.startswith("time:"))
    dp.message.register(my_bookings, lambda message: message.text == "📖 Мои брони")
    dp.message.register(show_admin_menu, lambda message: message.text == "⚙️ Админ")
    dp.message.register(handle_admin_action, lambda message: message.text == "❌ Отменить чужую бронь")
    dp.message.register(handle_admin_action, lambda message: message.text == "⬅️ Вернуться в главное меню")
    dp.message.register(view_bookings, lambda message: message.text == "📋 Посмотреть брони")
    dp.callback_query.register(show_bookings_for_date, lambda callback: callback.data.startswith("view_broni:"))
    dp.message.register(cancel_booking, lambda message: message.text == "❌ Отменить бронь")
    dp.callback_query.register(confirm_cancel, lambda callback: callback.data.startswith("cancel:"))