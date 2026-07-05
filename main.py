import asyncio
import calendar
import logging
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Токен вашего бота
TOKEN = "8854798148:AAG4271TEM_iNRJLyJJYK6ap0Okohq_ViSM"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Настройки статусов для отображения в меню и подсчета статистики часов
STATUSES = {
    "day": {"text": "Дневная смена (12ч)", "emoji": "🟡", "hours": 12},
    "day4": {"text": "Дневная смена (4ч)", "emoji": "🟡", "hours": 4},
    "night": {"text": "Ночная смена (12ч)", "emoji": "🔵", "hours": 12},
    "night4": {"text": "Ночная смена (4ч)", "emoji": "🔵", "hours": 4},
    "weekend": {"text": "Выходной", "emoji": "🔴", "hours": 0},
    "holiday": {"text": "Праздник", "emoji": "🟣", "hours": 0},
    "vacation": {"text": "Отпуск", "emoji": "🟠", "hours": 0},
}

# --- РАБОТА С БАЗОЙ ДАННЫХ SQLite ---
def init_db():
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS days_status (
            date_str TEXT PRIMARY KEY,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_month_statuses(year: int, month: int) -> dict:
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    prefix = f"{year}-{month:02d}-"
    cursor.execute("SELECT date_str, status FROM days_status WHERE date_str LIKE ?", (f"{prefix}%",))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def set_day_status(date_str: str, status: str):
    conn = sqlite3.connect("schedule.db")
    cursor = conn.cursor()
    if status == "clear":
        cursor.execute("DELETE FROM days_status WHERE date_str = ?", (date_str,))
    else:
        cursor.execute("""
            INSERT INTO days_status (date_str, status) VALUES (?, ?)
            ON CONFLICT(date_str) DO UPDATE SET status=excluded.status
        """, (date_str, status))
    conn.commit()
    conn.close()

# --- ГЕНЕРАЦИЯ ТЕКСТА СТАТИСТИКИ СМЕН ---
def get_stats_text(year: int, month: int, saved_statuses: dict) -> str:
    months_ru = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь", 
                 7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}
    
    counts = {k: 0 for k in STATUSES.keys()}
    total_hours = 0
    
    for status in saved_statuses.values():
        if status in counts:
            counts[status] += 1
            total_hours += STATUSES[status]["hours"]
            
    text = f"📅 *Календарь: {months_ru[month]} {year}*\n\n"
    text += f"🟡 Дневных смен (12ч): {counts['day']}\n"
    text += f"🟡 Дневных смен (4ч): {counts['day4']}\n"
    text += f"🔵 Ночных смен (12ч): {counts['night']}\n"
    text += f"🔵 Ночных смен (4ч): {counts['night4']}\n"
    text += f"🔴 Выходных: {counts['weekend']}\n"
    text += f"🟣 Праздников: {counts['holiday']}\n"
    text += f"🟠 Отпуск: {counts['vacation']}\n\n"
    text += f"⏱ *Всего отработано:* {total_hours} ч.\n\n"
    text += "Нажмите на любое число, чтобы изменить его цвет и статус:"
    return text

# --- ГЕНЕРАТОР КНОПОК ИНТЕРАКТИВНОГО КАЛЕНДАРЯ ---
def create_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    saved_statuses = get_month_statuses(year, month)
    keyboard = []

    # Ряд дней недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                date_key = f"{year}-{month:02d}-{day:02d}"
                if date_key in saved_statuses:
                    status_type = saved_statuses[date_key]
                    emoji = STATUSES[status_type]["emoji"]
                    btn_text = f"{emoji} {day}"
                else:
                    btn_text = str(day)
                row.append(InlineKeyboardButton(text=btn_text, callback_data=f"click_{year}_{month}_{day}"))
        keyboard.append(row)

    # Ряд кнопок навигации по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"change_{prev_year}_{prev_month}"),
        InlineKeyboardButton(text="Вперед ➡️", callback_data=f"change_{next_year}_{next_month}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ГЕНЕРАТОР МЕНЮ ВЫБОРА ЦВЕТА ---
def create_status_menu(year: int, month: int, day: int) -> InlineKeyboardMarkup:
    keyboard = []
    date_str = f"{year}-{month:02d}-{day:02d}"
    
    for status_key, info in STATUSES.items():
        keyboard.append([InlineKeyboardButton(text=f"{info['emoji']} {info['text']}", callback_data=f"set_{status_key}_{date_str}")])
        
    keyboard.append([InlineKeyboardButton(text="⚪ Сбросить цвет", callback_data=f"set_clear_{date_str}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к календарю", callback_data=f"change_{year}_{month}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ХЕНДЛЕРЫ СОБЫТИЙ ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    now = datetime.now()
    saved = get_month_statuses(now.year, now.month)
    text = get_stats_text(now.year, now.month, saved)
    await message.answer(text=text, parse_mode="Markdown", reply_markup=create_calendar(now.year, now.month))

@dp.callback_query(F.data.startswith("change_"))
async def process_month_change(callback: types.CallbackQuery):
    _, year, month = callback.data.split("_")
    year, month = int(year), int(month)
    saved = get_month_statuses(year, month)
    text = get_stats_text(year, month, saved)
    await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=create_calendar(year, month))
    await callback.answer()

@dp.callback_query(F.data.startswith("click_"))
async def process_date_click(callback: types.CallbackQuery):
    _, year, month, day = callback.data.split("_")
    year, month, day = int(year), int(month), int(day)
    await callback.message.edit_text(
        text=f"Выбери статус для даты: *{day:02d}.{month:02d}.{year}*",
        parse_mode="Markdown",
        reply_markup=create_status_menu(year, month, day)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("set_"))
async def process_status_set(callback: types.CallbackQuery):
    _, status_key, date_str = callback.data.split("_")
    set_day_status(date_str, status_key)
    year, month, _ = map(int, date_str.split("-"))
    saved = get_month_statuses(year, month)
    text = get_stats_text(year, month, saved)
    await callback.message.edit_text(text=text, parse_mode="Markdown", reply_markup=create_calendar(year, month))
    await callback.answer(text="Статус обновлен!")

@dp.callback_query(F.data == "ignore")
async def process_ignore(callback: types.CallbackQuery):
    await callback.answer()

# --- ОСНОВНОЙ ЗАПУСК ---
async def main():
    init_db()
    print("Бот успешно запущен и готов к работе!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

asyncio.run(main())
