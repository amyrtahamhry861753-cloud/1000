import os
import threading
from flask import Flask
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# -------------------------------------------------------------
# توکن ربات مدیریت نولکس
TOKEN = "8875197695:AAHZofQPyzAzNgp8UT4Ka6dOrKwUBipi1WQ"
bot = telebot.TeleBot(TOKEN)
# -------------------------------------------------------------

# سرور وب برای تایید سلامت سرویس در Render
app = Flask(__name__)


@app.route("/")
def home():
  return "Nolex Admin Bot is Online!"


def run_web():
  # دریافت پورت اختصاصی از محیط اجرای Render
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def keep_alive():
  # اجرای سرور وب در یک گرایش (Thread) جداگانه تا مزاحم کارکرد ربات نشود
  t = threading.Thread(target=run_web)
  t.daemon = True
  t.start()


# حافظه موقت دیتابیس ربات
filtered_words = {}
group_members = {}
user_states = {}


def is_admin_or_owner(chat_id, user_id):
  try:
    member = bot.get_chat_member(chat_id, user_id)
    return member.status in ["creator", "administrator"]
  except Exception:
    return False


def get_main_panel_keyboard():
  markup = InlineKeyboardMarkup(row_width=2)
  btn1 = InlineKeyboardButton(
      "🚫 حذف کاربران", callback_data="panel_kick_list"
  )
  btn2 = InlineKeyboardButton("🤬 فیلتر کلمات", callback_data="panel_filter")
  btn3 = InlineKeyboardButton(
      "🗑 حذف کلمات فیلتر", callback_data="panel_unfilter_list"
  )
  btn4 = InlineKeyboardButton("📖 راهنمای ربات", callback_data="panel_help")
  markup.add(btn1, btn2)
  markup.add(btn3, btn4)
  return markup


# ردیابی پیام‌ها و بررسی کلمات فیلترشده
@bot.message_handler(
    func=lambda message: True,
    content_types=["text", "photo", "sticker", "new_chat_members"],
)
def track_members_and_messages(message):
  chat_id = message.chat.id
  if message.chat.type == "private":
    return

  if chat_id not in group_members:
    group_members[chat_id] = {}

  user = message.from_user
  if not user.is_bot and not is_admin_or_owner(chat_id, user.id):
    group_members[chat_id][user.id] = user.first_name

  if message.text:
    text = message.text.strip()
    user_id = user.id
    words = filtered_words.get(chat_id, [])

    # چک کردن کلمات ممنوعه
    for w in words:
      if w in text.lower():
        try:
          bot.delete_message(chat_id, message.message_id)
          bot.ban_chat_member(chat_id, user_id)
          bot.send_message(
              chat_id,
              f"🚫 کاربر {user.first_name} به دلیل ارسال کلمه فیلتر شده از"
              " گروه اخراج شد.",
          )
        except Exception:
          pass
        return

    # افزودن کلمه جدید به لیست فیلتر
    if user_id in user_states and user_states[user_id].get(
        "action"
    ) == "wait_filter":
      bad_word = text.lower()
      if chat_id not in filtered_words:
        filtered_words[chat_id] = []
      if bad_word not in filtered_words[chat_id]:
        filtered_words[chat_id].append(bad_word)
        bot.reply_to(
            message,
            f"✅ کلمه **{bad_word}** به لیست فیلتر اضافه شد.",
            parse_mode="Markdown",
        )
      del user_states[user_id]


# دستور start در پیوی
@bot.message_handler(commands=["start"], chat_types=["private"])
def send_welcome_private(message):
  bot_username = bot.get_me().username
  text = (
      "سلام! من **نولکس مدیریت** هستم. با من می‌تونی گروه‌تو مدیریت کنی! ⚡️"
  )
  markup = InlineKeyboardMarkup()
  add_to_group_url = f"https://t.me/{bot_username}?startgroup=true&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages"
  markup.add(
      InlineKeyboardButton("➕ پیوستن ربات به گروه", url=add_to_group_url)
  )
  bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")


# عضویت ربات در گروه
@bot.message_handler(content_types=["new_chat_members"])
def on_join_group(message):
  bot_id = bot.get_me().id
  for member in message.new_chat_members:
    if member.id == bot_id:
      text = "سلام! برای مدیریت گروه، گزینه‌ها را انتخاب کنید:"
      bot.send_message(
          message.chat.id, text, reply_markup=get_main_panel_keyboard()
      )


# مدیریت کلیک دکمه‌ها
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
  chat_id = call.message.chat.id
  user_id = call.from_user.id
  if not is_admin_or_owner(chat_id, user_id):
    bot.answer_callback_query(
        call.id, "❌ این پنل فقط برای ادمین‌هاست!", show_alert=True
    )
    return
  bot.answer_callback_query(call.id)

  if call.data == "main_menu":
    bot.edit_message_text(
        "سلام! برای مدیریت، گزینه‌ها را انتخاب کنید:",
        chat_id,
        call.message.message_id,
        reply_markup=get_main_panel_keyboard(),
    )
  elif call.data == "panel_kick_list":
    members = group_members.get(chat_id, {})
    markup = InlineKeyboardMarkup(row_width=1)
    if not members:
      markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
      bot.edit_message_text(
          "کاربر جدیدی ثبت نشده است.",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
      return
    for m_id, m_name in list(members.items()):
      markup.add(
          InlineKeyboardButton(
              f"❌ حذف {m_name}", callback_data=f"kick_user_{m_id}"
          )
      )
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    bot.edit_message_text(
        "روی هر کاربر بزنید تا از گروه حذف شود:",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
    )
  elif call.data.startswith("kick_user_"):
    target_id = int(call.data.replace("kick_user_", ""))
    try:
      bot.ban_chat_member(chat_id, target_id)
      if target_id in group_members.get(chat_id, {}):
        del group_members[chat_id][target_id]
      bot.send_message(chat_id, "✅ کاربر با موفقیت اخراج شد.")
      handle_callbacks(call)
    except Exception:
      bot.send_message(chat_id, "❌ خطا در اخراج کاربر.")
  elif call.data == "panel_filter":
    user_states[user_id] = {"action": "wait_filter", "chat_id": chat_id}
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    bot.edit_message_text(
        "کلمه مورد نظر برای فیلتر را بفرستید:",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
    )
  elif call.data == "panel_unfilter_list":
    words = filtered_words.get(chat_id, [])
    markup = InlineKeyboardMarkup()
    if not words:
      markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
      bot.edit_message_text(
          "هیچ کلمه‌ای فیلتر نشده است.",
          chat_id,
          call.message.message_id,
          reply_markup=markup,
      )
      return
    for word in words:
      markup.add(
          InlineKeyboardButton(
              f"🗑 حذف: {word}", callback_data=f"remove_word_{word}"
          )
      )
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    bot.edit_message_text(
        "برای حذف فیلتر روی کلمه کلیک کنید:",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
    )
  elif call.data.startswith("remove_word_"):
    word_to_remove = call.data.replace("remove_word_", "")
    if chat_id in filtered_words and word_to_remove in filtered_words[chat_id]:
      filtered_words[chat_id].remove(word_to_remove)
      bot.send_message(chat_id, f"✅ کلمه **{word_to_remove}** از فیلتر حذف شد.")
  elif call.data == "panel_help":
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu"))
    bot.edit_message_text(
        "📖 راهنمای پنل مدیریت گروه نولکس.",
        chat_id,
        call.message.message_id,
        reply_markup=markup,
    )


# --- اجرای برنامه ---
if __name__ == "__main__":
  keep_alive()
  print("Nolex Admin Bot is starting...")
  bot.infinity_polling(skip_pending_updates=True)
  
