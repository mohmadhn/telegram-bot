import telebot
from telebot import types
import time
import sqlite3
from datetime import datetime
from collections import defaultdict

API_TOKEN = "7877693917:AAGIF9k8KOSpwJy3DTr3M8qvQyufwf5TeLA"
bot = telebot.TeleBot(API_TOKEN)

# اتصال به دیتابیس SQLite و ایجاد جدول در صورت عدم وجود
def init_db():
    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    # اگر جدول قبلی داری، اگه ستون user_id نبود باید تغییرش بدی (یا حذف کنی فایل db)
    c.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        category TEXT,
        item TEXT,
        amount INTEGER,
        date TEXT
    )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- منوی اصلی --- #
def show_main_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("➕ ثبت هزینه", callback_data='add_expense'))
    markup.row(types.InlineKeyboardButton("📊 گزارش کلی", callback_data='show_report'))
    markup.row(types.InlineKeyboardButton("📋 لیست هزینه‌ها", callback_data='list_expenses'))
    bot.send_message(chat_id, "لطفاً یکی از گزینه‌ها رو انتخاب کن:", reply_markup=markup)

# --- /start --- #
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, f"سلام {message.from_user.first_name}!\nبه ربات حسابداری خانواده خوش اومدی ✨")
    show_main_menu(message.chat.id)

# --- دکمه‌ها --- #
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = str(call.from_user.id)

    if call.data == 'add_expense':
        # منوی دسته بندی با دکمه برای ثبت هزینه
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        categories = ['خوراک', 'حمل‌ونقل', 'درمان', 'آموزش', 'تفریح', 'متفرقه']
        for cat in categories:
            markup.add(cat)
        msg = bot.send_message(call.message.chat.id, "دسته هزینه رو انتخاب کن:", reply_markup=markup)
        bot.register_next_step_handler(msg, process_category, user_id)

    elif call.data == 'show_report':
        conn = sqlite3.connect("expenses.db")
        c = conn.cursor()
        c.execute("SELECT category, item, amount FROM expenses WHERE user_id=? ORDER BY id DESC", (user_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            bot.send_message(call.message.chat.id, "هیچ هزینه‌ای ثبت نشده.")
            return

        text = "📊 گزارش کلی هزینه‌ها:\n\n"
        total = 0
        categories = {}

        for i, row in enumerate(rows, 1):
            category, item, amount = row
            text += f"{i}. [{category}] {item} - {amount} تومان\n"
            total += amount
            categories[category] = categories.get(category, 0) + amount

        text += "\n📂 جمع هزینه‌ها بر اساس دسته:\n"
        for cat, val in categories.items():
            text += f"🔹 {cat}: {val} تومان\n"

        text += f"\n💰 مجموع کل: {total} تومان"
        bot.send_message(call.message.chat.id, text)

    elif call.data == 'list_expenses':
        send_expense_categories(call.message.chat.id, user_id)

    elif call.data.startswith("list_cat_"):
        cat = call.data[len("list_cat_"):]
        send_expenses_in_category(call.message.chat.id, user_id, cat)

    elif call.data.startswith("delete_"):
        expense_id = int(call.data.split("_")[1])
        conn = sqlite3.connect("expenses.db")
        c = conn.cursor()
        c.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        conn.commit()
        conn.close()
        bot.answer_callback_query(call.id, "✅ حذف شد.")
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text="❌ این هزینه حذف شد.")
        # بعد حذف، بریم لیست دسته‌ها
        send_expense_categories(call.message.chat.id, user_id)

    elif call.data.startswith("edit_"):
        expense_id = int(call.data.split("_")[1])
        edit_sessions[user_id]["expense_id"] = expense_id
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "لطفاً مقدار جدید رو به این صورت وارد کن:\n\n`دسته عنوان مبلغ`\nمثال:\nخوراک نان 35000", parse_mode="Markdown")

# --- ثبت هزینه مرحله دسته --- #
def process_category(message, user_id):
    category = message.text.strip()
    valid_categories = ['خوراک', 'حمل‌ونقل', 'درمان', 'آموزش', 'تفریح', 'متفرقه']
    if category not in valid_categories:
        msg = bot.send_message(message.chat.id, f"دسته نامعتبر است. لطفا یکی از دسته‌های زیر را انتخاب کن:\n{', '.join(valid_categories)}")
        bot.register_next_step_handler(msg, process_category, user_id)
        return

    msg = bot.send_message(message.chat.id, "حالا عنوان و مبلغ هزینه رو وارد کن، مثلا:\nنان 20000")
    bot.register_next_step_handler(msg, process_expense, user_id, category)

# --- ثبت هزینه مرحله عنوان و مبلغ --- #
def process_expense(message, user_id, category):
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            raise ValueError("فرمت اشتباهه")
        item = " ".join(parts[:-1])
        amount = int(parts[-1])
    except:
        msg = bot.send_message(message.chat.id, "فرمت اشتباهه. لطفا عنوان و مبلغ رو دوباره وارد کن مثل:\nنان 20000")
        bot.register_next_step_handler(msg, process_expense, user_id, category)
        return

    date = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute("INSERT INTO expenses (user_id, category, item, amount, date) VALUES (?, ?, ?, ?, ?)",
              (user_id, category, item, amount, date))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, f"✅ هزینه '{item}' به مبلغ {amount} تومان در دسته [{category}] ثبت شد.")
    show_main_menu(message.chat.id)

# --- ارسال لیست دسته‌بندی‌ها --- #
def send_expense_categories(chat_id, user_id):
    markup = types.InlineKeyboardMarkup()
    categories = ['خوراک', 'حمل‌ونقل', 'درمان', 'آموزش', 'تفریح', 'متفرقه']
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat, callback_data=f"list_cat_{cat}"))
    bot.send_message(chat_id, "دسته‌بندی هزینه‌ها:", reply_markup=markup)

# --- ارسال هزینه‌ها در دسته خاص با دکمه‌های حذف و ویرایش --- #
def send_expenses_in_category(chat_id, user_id, category):
    conn = sqlite3.connect("expenses.db")
    c = conn.cursor()
    c.execute("SELECT id, item, amount FROM expenses WHERE user_id=? AND category=? ORDER BY id DESC", (user_id, category))
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.send_message(chat_id, f"هیچ هزینه‌ای در دسته [{category}] ثبت نشده.")
        return

    for row in rows:
        expense_id, item, amount = row
        text = f"[{category}] {item} - {amount} تومان"
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🗑 حذف", callback_data=f"delete_{expense_id}"),
            types.InlineKeyboardButton("✏ ویرایش", callback_data=f"edit_{expense_id}")
        )
        bot.send_message(chat_id, text, reply_markup=markup)

# --- ویرایش هزینه --- #
edit_sessions = defaultdict(dict)

@bot.message_handler(func=lambda message: str(message.from_user.id) in edit_sessions)
def handle_edit_input(message):
    user_id = str(message.from_user.id)
    try:
        parts = message.text.strip().split()
        if len(parts) < 3:
            raise ValueError("فرمت اشتباهه")

        category = parts[0]
        item = " ".join(parts[1:-1])
        amount = int(parts[-1])

        expense_id = edit_sessions[user_id]["expense_id"]

        conn = sqlite3.connect("expenses.db")
        c = conn.cursor()
        c.execute("UPDATE expenses SET category=?, item=?, amount=? WHERE id=? AND user_id=?",
                  (category, item, amount, expense_id, user_id))
        conn.commit()
        conn.close()

        bot.send_message(message.chat.id, "✅ با موفقیت ویرایش شد.")
        del edit_sessions[user_id]

    except Exception as e:
        bot.send_message(message.chat.id, "❌ ورودی نامعتبره. لطفاً دوباره امتحان کن.")

# --- اجرای امن ربات (سازگار با Spyder و همیشه آنلاین) --- #
def run_bot():
    print("ربات در حال اجراست... (SQLite فعال)")
    while True:
        try:
            bot.polling(non_stop=True)
        except Exception as e:
            print("خطا:", e)
            time.sleep(10)

if __name__ == "__main__":
    run_bot()
