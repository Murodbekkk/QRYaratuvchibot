# =========================================================
# MURODBEK PROFESSIONAL QR BOT — TO'LIQ MUKAMMAL VERSIYA
# =========================================================
# INSTALL:
# pip install pyTelegramBotAPI qrcode pillow pyzbar opencv-python
# =========================================================

# =========================================================
# CONFIG
# =========================================================
TOKEN = "8608839152:AAF2BTh1h1ppv8J56ZX8Oy2vAkzr69gv7EY"
OWNER_ID = 8133971943
# Boshlang'ich kanal (keyinchalik Telegramdan qo'shish/o'chirish mumkin)
DEFAULT_CHANNELS = ["@murodbek_rashidov"]
# =========================================================
# IMPORTS
# =========================================================
import telebot
from telebot import types
import sqlite3
import os
import time
import io
from datetime import datetime
from PIL import Image
import cv2
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
import qrcode

def generate_qr(text):
    qr = qrcode.make(text)
    qr.save("qr_code.png")  # Yaratilgan QR kodini fayl sifatida saqlash
# =========================================================
# BOT
# =========================================================

bot = telebot.TeleBot(TOKEN)

# =========================================================
# DATABASE
# =========================================================

conn   = sqlite3.connect("qrbot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id     INTEGER PRIMARY KEY,
    full_name   TEXT,
    phone       TEXT,
    username    TEXT,
    joined_date TEXT
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins(
    user_id INTEGER PRIMARY KEY
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS qr_history(
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    qr_text      TEXT,
    created_date TEXT
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS banned_users(
    user_id     INTEGER PRIMARY KEY,
    reason      TEXT,
    banned_date TEXT
)""")

# Kanallar dinamik boshqariladi
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels(
    channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE
)""")

# Boshlang'ich kanallarni qo'sh (agar yo'q bo'lsa)
for ch in DEFAULT_CHANNELS:
    cursor.execute(
        "INSERT OR IGNORE INTO channels(username) VALUES(?)",
        (ch,)
    )

conn.commit()

# =========================================================
# KANAL HELPER
# =========================================================

def get_channels() -> list:
    cursor.execute("SELECT username FROM channels")
    return [row[0] for row in cursor.fetchall()]

# =========================================================
# RATE LIMITING
# =========================================================

_last_action: dict = {}
RATE_LIMIT_SEC = 2

def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    if user_id in _last_action:
        if now - _last_action[user_id] < RATE_LIMIT_SEC:
            return True
    _last_action[user_id] = now
    return False

# =========================================================
# ROLE HELPERS
# =========================================================

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def is_banned(user_id: int) -> bool:
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

# =========================================================
# GUARD
# =========================================================

def guard(message) -> bool:
    uid = message.from_user.id
    if is_banned(uid):
        bot.send_message(message.chat.id, "🚫 Siz botdan bloklangansiz.")
        return False
    if is_rate_limited(uid):
        bot.send_message(message.chat.id, "⏳ Iltimos biroz kuting (spam himoya).")
        return False
    return True

# =========================================================
# MAJBURIY OBUNA
# =========================================================

def check_sub(user_id: int) -> bool:
    for ch in get_channels():
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            print(f"[check_sub] {e}")
            return False
    return True

def sub_keyboard():
    markup = types.InlineKeyboardMarkup()
    for ch in get_channels():
        markup.add(
            types.InlineKeyboardButton(
                f"📢 {ch} — Obuna bo'lish",
                url=f"https://t.me/{ch.lstrip('@')}"
            )
        )
    markup.add(
        types.InlineKeyboardButton("✅ Obuna bo'ldim — Tekshirish", callback_data="check_sub")
    )
    return markup

# =========================================================
# CANCEL HELPER
# =========================================================

def cancel_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    m.add("❌ Bekor")
    return m

def is_cancel(msg) -> bool:
    return bool(msg.text and msg.text.strip() == "❌ Bekor")

# =========================================================
# MAIN MENU  (admin/ega uchun qo'shimcha tugmalar)
# =========================================================

def main_menu(chat_id, user_id=None):
    if user_id is None:
        user_id = chat_id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📷 QR Kod Yaratish", "🎨 Rangli QR")
    markup.row("🖼 Rasm QR O'qish")
    markup.row("👤 Profil", "📜 Tarix")
    markup.row("🗑 Tarixni Tozalash", "ℹ️ Bot Haqida")

    # Admin/ega uchun bosh sahifada panel tugmasi
    if is_owner(user_id):
        markup.row("👑 Ega Paneli")
    elif is_admin(user_id):
        markup.row("🛠 Admin Paneli")

    bot.send_message(chat_id, "🏠 Asosiy Menu", reply_markup=markup)

# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):
    if not guard(message):
        return

    uid = message.from_user.id

    if not check_sub(uid):
        bot.send_message(
            message.chat.id,
            (
                "👋 Xush kelibsiz!\n\n"
                "❗ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:"
            ),
            reply_markup=sub_keyboard()
        )
        return

    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))
    if cursor.fetchone():
        main_menu(message.chat.id, uid)
        return

    msg = bot.send_message(
        message.chat.id,
        "👋 Xush kelibsiz!\n\n👤 Ism Familiyangizni kiriting:",
        reply_markup=cancel_kb()
    )
    bot.register_next_step_handler(msg, get_name)

# =========================================================
# REGISTRATION
# =========================================================

def get_name(message):
    if is_cancel(message):
        bot.send_message(message.chat.id, "❌ Bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())
        return
    full_name = message.text.strip()
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    m.add(types.KeyboardButton("📱 Telefon Raqam Yuborish", request_contact=True))
    m.add("❌ Bekor")
    msg = bot.send_message(message.chat.id, "📞 Telefon raqamingizni yuboring:", reply_markup=m)
    bot.register_next_step_handler(msg, lambda x: save_user(x, full_name))

def save_user(message, full_name):
    if is_cancel(message):
        bot.send_message(message.chat.id, "❌ Bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())
        return
    if not message.contact:
        msg = bot.send_message(message.chat.id, "❌ Iltimos tugma orqali telefon yuboring.", reply_markup=cancel_kb())
        bot.register_next_step_handler(msg, lambda x: save_user(x, full_name))
        return
    uid  = message.from_user.id
    user = message.from_user.username
    phone = message.contact.phone_number
    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?)",
        (uid, full_name, phone, user, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    bot.send_message(message.chat.id, "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!", reply_markup=types.ReplyKeyboardRemove())
    main_menu(message.chat.id, uid)

# =========================================================
# QR — ODDIY
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📷 QR Kod Yaratish")
def qr_create(message):
    if not guard(message):
        return
    msg = bot.send_message(message.chat.id, "✍️ Matn yoki link yuboring:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, generate_qr)

def generate_qr(message):
    if is_cancel(message):
        main_menu(message.chat.id, message.from_user.id)
        return
    text = message.text
    qr  = qrcode.make(text)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    _save_qr_history(message.from_user.id, text)
    bot.send_photo(message.chat.id, buf, caption="✅ QR Kod tayyor!")

# =========================================================
# QR — RANGLI
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🎨 Rangli QR")
def qr_colored_menu(message):
    if not guard(message):
        return
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔵 Ko'k",       callback_data="qrc_#1565C0"),
        types.InlineKeyboardButton("🔴 Qizil",      callback_data="qrc_#C62828"),
        types.InlineKeyboardButton("🟢 Yashil",     callback_data="qrc_#2E7D32"),
        types.InlineKeyboardButton("🟣 Binafsha",   callback_data="qrc_#6A1B9A"),
        types.InlineKeyboardButton("🟠 To'q sariq", callback_data="qrc_#E65100"),
        types.InlineKeyboardButton("⚫ Qora (oddiy)",callback_data="qrc_#000000"),
    )
    bot.send_message(message.chat.id, "🎨 Rang tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("qrc_"))
def qrc_selected(call):
    color = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"Rang: {color}")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "✍️ Matn yoki link yuboring:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, lambda m: generate_colored_qr(m, color))

def generate_colored_qr(message, fill_color):
    if is_cancel(message):
        main_menu(message.chat.id, message.from_user.id)
        return
    text   = message.text
    qr_obj = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr_obj.add_data(text)
    qr_obj.make(fit=True)
    img = qr_obj.make_image(fill_color=fill_color, back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    _save_qr_history(message.from_user.id, text)
    bot.send_photo(message.chat.id, buf, caption=f"✅ Rangli QR tayyor!\n🎨 Rang: <code>{fill_color}</code>", parse_mode="HTML")

# =========================================================
# QR — O'QISH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🖼 Rasm QR O'qish")
def qr_read_prompt(message):
    if not guard(message):
        return
    bot.send_message(message.chat.id, "🖼 QR kod rasmini yuboring:", reply_markup=cancel_kb())

@bot.message_handler(content_types=["photo"])
def decode_qr(message):
    if not guard(message):
        return
    try:
        fi   = bot.get_file(message.photo[-1].file_id)
        data_bytes = bot.download_file(fi.file_path)
        fname = f"{message.from_user.id}_qr.png"
        with open(fname, "wb") as f:
            f.write(data_bytes)

        result = None

        # 1-urinish: OpenCV
        img = cv2.imread(fname)
        det = cv2.QRCodeDetector()
        val, _, _ = det.detectAndDecode(img)
        if val:
            result = val

        # 2-urinish: pyzbar
        if not result and PYZBAR_AVAILABLE:
            pil = Image.open(fname)
            decoded = pyzbar_decode(pil)
            if decoded:
                result = decoded[0].data.decode("utf-8")

        os.remove(fname)

        if result:
            bot.send_message(
                message.chat.id,
                f"✅ QR kod o'qildi:\n\n<code>{result}</code>",
                parse_mode="HTML"
            )
        else:
            bot.send_message(message.chat.id, "❌ QR kod topilmadi. Rasmni aniqroq yuboring.")

    except Exception as e:
        print(e)
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi.")

# =========================================================
# PROFIL
# =========================================================

@bot.message_handler(func=lambda m: m.text == "👤 Profil")
def profile(message):
    if not guard(message):
        return
    cursor.execute("SELECT * FROM users WHERE user_id=?", (message.from_user.id,))
    u = cursor.fetchone()
    if not u:
        bot.send_message(message.chat.id, "❌ Profil topilmadi. /start bosing.")
        return
    cursor.execute("SELECT COUNT(*) FROM qr_history WHERE user_id=?", (message.from_user.id,))
    qr_count = cursor.fetchone()[0]
    bot.send_message(
        message.chat.id,
        f"👤 <b>Profil</b>\n\n"
        f"📛 Ism: <b>{u[1]}</b>\n"
        f"📱 Telefon: <b>{u[2]}</b>\n"
        f"🔗 Username: @{u[3] or '—'}\n"
        f"🆔 ID: <code>{u[0]}</code>\n"
        f"📅 Sana: {u[4]}\n"
        f"📷 Jami QR: <b>{qr_count}</b> ta",
        parse_mode="HTML"
    )

# =========================================================
# TARIX
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📜 Tarix")
def history(message):
    if not guard(message):
        return
    cursor.execute(
        "SELECT qr_text, created_date FROM qr_history WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (message.from_user.id,)
    )
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Tarix topilmadi.")
        return
    text = "📜 <b>Oxirgi 10 QR:</b>\n\n"
    for i, (qt, dt) in enumerate(rows, 1):
        text += f"{i}. <code>{qt}</code>\n   🕒 {dt}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# =========================================================
# TARIXNI TOZALASH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🗑 Tarixni Tozalash")
def clear_history_ask(message):
    if not guard(message):
        return
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Ha, o'chir",  callback_data="clr_yes"),
        types.InlineKeyboardButton("❌ Yo'q, bekor", callback_data="clr_no")
    )
    bot.send_message(message.chat.id, "⚠️ Barcha QR tarixingiz o'chiriladi. Tasdiqlaysizmi?", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ("clr_yes", "clr_no"))
def clear_history_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.data == "clr_yes":
        cursor.execute("DELETE FROM qr_history WHERE user_id=?", (call.from_user.id,))
        conn.commit()
        bot.send_message(call.message.chat.id, "✅ Tarix tozalandi.")
    else:
        bot.send_message(call.message.chat.id, "❌ Bekor qilindi.")

# =========================================================
# ABOUT
# =========================================================

@bot.message_handler(func=lambda m: m.text == "ℹ️ Bot Haqida")
def about(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>PROFESSIONAL QR BOT</b>\n\n"
        "✅ QR yaratish (oddiy + rangli)\n"
        "✅ Rasm QR o'qish\n"
        "✅ Profil va tarix\n"
        "✅ Admin / Ega paneli\n"
        "✅ Dinamik kanal boshqaruvi\n"
        "✅ Ban / Unban tizimi\n"
        "✅ Broadcast (rasm + matn)\n"
        "✅ Spam himoya\n"
        "✅ Foydalanuvchi qidirish va eksport\n\n"
        "👨‍💻 Developer: <b>Murodbek</b>",
        parse_mode="HTML"
    )

# =========================================================
#  ██████╗  ██████╗  ██████╗  █████╗ ██╗
# ██╔═══██╗██╔═══██╗██╔════╝ ██╔══██╗██║
# ██║   ██║██║   ██║██║  ███╗███████║██║
# ██║   ██║██║   ██║██║   ██║██╔══██║╚═╝
#  ██████╔╝╚██████╔╝╚██████╔╝██║  ██║██╗
#  ╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝
# =========================================================

def owner_panel_kb(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👥 Userlar",     "🔍 Qidirish")
    markup.row("📊 Statistika",  "📤 Eksport")
    markup.row("📢 Broadcast",   "💬 Xabar Yuborish")
    markup.row("🛡 Adminlar",    "➕ Admin Qo'shish", "➖ Admin O'chirish")
    markup.row("🔨 Ban",         "🔓 Unban",           "🚫 Banlist")
    markup.row("📡 Kanallar",    "➕ Kanal Qo'sh",    "➖ Kanal O'chir")
    markup.row("🏠 Asosiy Menu")
    bot.send_message(chat_id, "👑 EGA PANELI", reply_markup=markup)

def admin_panel_kb(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("👥 Userlar",    "🔍 Qidirish")
    markup.row("📊 Statistika", "📤 Eksport")
    markup.row("📢 Broadcast",  "💬 Xabar Yuborish")
    markup.row("🏠 Asosiy Menu")
    bot.send_message(chat_id, "🛠 ADMIN PANELI", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👑 Ega Paneli")
def open_owner_panel(message):
    if not is_owner(message.from_user.id):
        return
    owner_panel_kb(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🛠 Admin Paneli")
def open_admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    if is_owner(message.from_user.id):
        owner_panel_kb(message.chat.id)
    else:
        admin_panel_kb(message.chat.id)

@bot.message_handler(commands=["panel"])
def panel_cmd(message):
    if not is_admin(message.from_user.id):
        return
    if is_owner(message.from_user.id):
        owner_panel_kb(message.chat.id)
    else:
        admin_panel_kb(message.chat.id)

@bot.message_handler(func=lambda m: m.text == "🏠 Asosiy Menu")
def back_main(message):
    main_menu(message.chat.id, message.from_user.id)

# =========================================================
# STATISTIKA
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def statistics(message):
    if not is_admin(message.from_user.id):
        return
    today = datetime.now().strftime("%d.%m.%Y")
    cursor.execute("SELECT COUNT(*) FROM users")
    total_u = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE joined_date LIKE ?", (f"{today}%",))
    today_u = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM qr_history")
    total_q = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM qr_history WHERE created_date LIKE ?", (f"{today}%",))
    today_q = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM admins")
    adm_c = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM banned_users")
    ban_c = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM channels")
    ch_c = cursor.fetchone()[0]
    bot.send_message(
        message.chat.id,
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Jami foydalanuvchi: <b>{total_u}</b>\n"
        f"📅 Bugun ro'yxat: <b>{today_u}</b>\n\n"
        f"📷 Jami QR: <b>{total_q}</b>\n"
        f"📅 Bugun QR: <b>{today_q}</b>\n\n"
        f"🛡 Adminlar: <b>{adm_c}</b>\n"
        f"🚫 Banlangan: <b>{ban_c}</b>\n"
        f"📡 Kanallar: <b>{ch_c}</b>",
        parse_mode="HTML"
    )

# =========================================================
# USERLAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "👥 Userlar")
def users_list(message):
    if not is_admin(message.from_user.id):
        return
    cursor.execute("SELECT user_id, full_name, phone, username FROM users")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Foydalanuvchi topilmadi.")
        return
    text = f"👥 <b>FOYDALANUVCHILAR ({len(rows)} ta):</b>\n\n"
    for u in rows:
        text += f"🆔 <code>{u[0]}</code> | 👤 {u[1]} | 📱 {u[2]}\n"
    for x in range(0, len(text), 4000):
        bot.send_message(message.chat.id, text[x:x+4000], parse_mode="HTML")

# =========================================================
# QIDIRISH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🔍 Qidirish")
def search_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🔍 ID yoki ism kiriting:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, search_user)

def search_user(message):
    if is_cancel(message):
        panel_cmd(message)
        return
    q = message.text.strip()
    if q.isdigit():
        cursor.execute("SELECT * FROM users WHERE user_id=?", (int(q),))
    else:
        cursor.execute("SELECT * FROM users WHERE full_name LIKE ?", (f"%{q}%",))
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Topilmadi.")
        return
    for u in rows[:5]:
        cursor.execute("SELECT COUNT(*) FROM qr_history WHERE user_id=?", (u[0],))
        qn = cursor.fetchone()[0]
        bot.send_message(
            message.chat.id,
            f"👤 <b>{u[1]}</b>\n"
            f"🆔 <code>{u[0]}</code>\n"
            f"📱 {u[2]}\n"
            f"🔗 @{u[3] or '—'}\n"
            f"📅 {u[4]}\n"
            f"📷 QR: <b>{qn}</b> ta",
            parse_mode="HTML"
        )

# =========================================================
# EKSPORT
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📤 Eksport")
def export_users(message):
    if not is_admin(message.from_user.id):
        return
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Foydalanuvchi yo'q.")
        return
    lines = ["ID | Ism | Telefon | Username | Sana", "-" * 55]
    for u in rows:
        lines.append(f"{u[0]} | {u[1]} | {u[2]} | @{u[3] or '—'} | {u[4]}")
    buf      = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.name = "users_export.txt"
    bot.send_document(message.chat.id, buf, caption=f"✅ Jami {len(rows)} ta foydalanuvchi")

# =========================================================
# BROADCAST  (matn + rasm + video)
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def broadcast_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(
        message.chat.id,
        "✍️ Reklama xabarini yuboring (matn, rasm+izoh yoki video):",
        reply_markup=cancel_kb()
    )
    bot.register_next_step_handler(msg, send_broadcast)

def send_broadcast(message):
    if is_cancel(message):
        panel_cmd(message)
        return
    cursor.execute("SELECT user_id FROM users")
    all_u = cursor.fetchall()
    ok = 0
    for (uid,) in all_u:
        try:
            if message.content_type == "photo":
                bot.send_photo(uid, message.photo[-1].file_id, caption=message.caption or "")
            elif message.content_type == "video":
                bot.send_video(uid, message.video.file_id, caption=message.caption or "")
            else:
                bot.send_message(uid, message.text)
            ok += 1
        except Exception:
            pass
    bot.send_message(message.chat.id, f"✅ Yuborildi: <b>{ok}</b> / {len(all_u)}", parse_mode="HTML")

# =========================================================
# FOYDALANUVCHIGA XABAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "💬 Xabar Yuborish")
def msg_user_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Foydalanuvchi ID si:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, msg_user_id)

def msg_user_id(message):
    if is_cancel(message):
        panel_cmd(message)
        return
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    tid = int(message.text)
    msg = bot.send_message(message.chat.id, "✍️ Xabar matni:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, lambda m: msg_user_send(m, tid))

def msg_user_send(message, tid):
    if is_cancel(message):
        panel_cmd(message)
        return
    try:
        bot.send_message(tid, f"📩 <b>Admin xabari:</b>\n\n{message.text}", parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ Xabar yuborildi.")
    except Exception:
        bot.send_message(message.chat.id, "❌ Xabar yuborib bo'lmadi (user botni bloklagan bo'lishi mumkin).")

# =========================================================
# ADMINLAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🛡 Adminlar")
def show_admins(message):
    if not is_owner(message.from_user.id):
        return
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Admin mavjud emas.")
        return
    text = "🛡 <b>ADMINLAR:</b>\n\n"
    for (aid,) in rows:
        text += f"🆔 <code>{aid}</code>\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "➕ Admin Qo'shish")
def add_admin_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Yangi admin ID si:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, save_admin)

def save_admin(message):
    if is_cancel(message):
        owner_panel_kb(message.chat.id)
        return
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    cursor.execute("INSERT OR REPLACE INTO admins VALUES(?)", (int(message.text),))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ Admin qo'shildi: <code>{message.text}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "➖ Admin O'chirish")
def del_admin_menu(message):
    if not is_owner(message.from_user.id):
        return
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Admin mavjud emas.")
        return
    markup = types.InlineKeyboardMarkup()
    for (aid,) in rows:
        markup.add(
            types.InlineKeyboardButton(
                f"🗑 {aid} ni o'chir",
                callback_data=f"deladm_{aid}"
            )
        )
    markup.add(types.InlineKeyboardButton("❌ Bekor", callback_data="deladm_cancel"))
    bot.send_message(message.chat.id, "🛡 O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("deladm_"))
def del_admin_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.data == "deladm_cancel":
        return
    aid = int(call.data.split("_", 1)[1])
    cursor.execute("DELETE FROM admins WHERE user_id=?", (aid,))
    conn.commit()
    bot.send_message(call.message.chat.id, f"✅ Admin o'chirildi: <code>{aid}</code>", parse_mode="HTML")

# =========================================================
# BAN / UNBAN / BANLIST
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🔨 Ban")
def ban_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Ban qilinadigan user ID:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, ban_get_id)

def ban_get_id(message):
    if is_cancel(message):
        owner_panel_kb(message.chat.id)
        return
    if not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    tid = int(message.text)
    msg = bot.send_message(message.chat.id, "📝 Ban sababi:", reply_markup=cancel_kb())
    bot.register_next_step_handler(msg, lambda m: ban_apply(m, tid))

def ban_apply(message, tid):
    if is_cancel(message):
        owner_panel_kb(message.chat.id)
        return
    reason = message.text
    cursor.execute(
        "INSERT OR REPLACE INTO banned_users VALUES(?,?,?)",
        (tid, reason, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    bot.send_message(message.chat.id, f"✅ <code>{tid}</code> bloklandi.\nSabab: {reason}", parse_mode="HTML")
    try:
        bot.send_message(tid, f"🚫 Siz botdan bloklandi.\nSabab: {reason}")
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.text == "🔓 Unban")
def unban_menu(message):
    if not is_owner(message.from_user.id):
        return
    cursor.execute("SELECT user_id, reason FROM banned_users")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "✅ Banlangan user yo'q.")
        return
    markup = types.InlineKeyboardMarkup()
    for (uid, reason) in rows:
        markup.add(
            types.InlineKeyboardButton(
                f"🔓 {uid} — {reason[:20]}",
                callback_data=f"unban_{uid}"
            )
        )
    markup.add(types.InlineKeyboardButton("❌ Bekor", callback_data="unban_cancel"))
    bot.send_message(message.chat.id, "🔓 Unban qilmoqchi bo'lgan userni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("unban_"))
def unban_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.data == "unban_cancel":
        return
    uid = int(call.data.split("_", 1)[1])
    cursor.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
    conn.commit()
    bot.send_message(call.message.chat.id, f"✅ <code>{uid}</code> unban qilindi.", parse_mode="HTML")
    try:
        bot.send_message(uid, "✅ Siz botdan blok olindi! Qayta foydalana olasiz.")
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.text == "🚫 Banlist")
def banlist(message):
    if not is_owner(message.from_user.id):
        return
    cursor.execute("SELECT user_id, reason, banned_date FROM banned_users")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "✅ Banlangan user yo'q.")
        return
    text = f"🚫 <b>BANLANGAN USERLAR ({len(rows)} ta):</b>\n\n"
    for (uid, reason, bdate) in rows:
        text += f"🆔 <code>{uid}</code>\n📝 {reason}\n📅 {bdate}\n\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# =========================================================
# 📡 KANAL BOSHQARUVI  ── YANGI (dinamik)
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📡 Kanallar")
def show_channels(message):
    if not is_owner(message.from_user.id):
        return
    channels = get_channels()
    if not channels:
        bot.send_message(message.chat.id, "❌ Hech qanday kanal yo'q.")
        return
    markup = types.InlineKeyboardMarkup()
    for ch in channels:
        markup.add(
            types.InlineKeyboardButton(
                f"📢 {ch}",
                url=f"https://t.me/{ch.lstrip('@')}"
            )
        )
    bot.send_message(
        message.chat.id,
        f"📡 <b>MAJBURIY OBUNA KANALLARI ({len(channels)} ta):</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "➕ Kanal Qo'sh")
def add_channel_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(
        message.chat.id,
        "📡 Kanal username kiriting:\nMisol: <code>@kanalname</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )
    bot.register_next_step_handler(msg, add_channel_save)

def add_channel_save(message):
    if is_cancel(message):
        owner_panel_kb(message.chat.id)
        return
    username = message.text.strip()
    if not username.startswith("@"):
        username = "@" + username

    # Kanal mavjudligini tekshir
    try:
        chat = bot.get_chat(username)
        title = chat.title
    except Exception:
        bot.send_message(
            message.chat.id,
            "❌ Kanal topilmadi. Username to'g'ri ekanligini va bot kanalga qo'shilganligini tekshiring."
        )
        return

    cursor.execute("INSERT OR IGNORE INTO channels(username) VALUES(?)", (username,))
    conn.commit()
    bot.send_message(
        message.chat.id,
        f"✅ Kanal qo'shildi!\n📢 <b>{title}</b>\n🔗 {username}",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "➖ Kanal O'chir")
def del_channel_menu(message):
    if not is_owner(message.from_user.id):
        return
    channels = get_channels()
    if not channels:
        bot.send_message(message.chat.id, "❌ O'chiriladigan kanal yo'q.")
        return
    markup = types.InlineKeyboardMarkup()
    for ch in channels:
        markup.add(
            types.InlineKeyboardButton(
                f"🗑 {ch} ni o'chir",
                callback_data=f"delch_{ch}"
            )
        )
    markup.add(types.InlineKeyboardButton("❌ Bekor", callback_data="delch_cancel"))
    bot.send_message(
        message.chat.id,
        "📡 O'chirmoqchi bo'lgan kanalni tanlang:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("delch_"))
def del_channel_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.data == "delch_cancel":
        return
    ch = call.data.split("_", 1)[1]
    cursor.execute("DELETE FROM channels WHERE username=?", (ch,))
    conn.commit()
    bot.send_message(
        call.message.chat.id,
        f"✅ Kanal o'chirildi: <code>{ch}</code>",
        parse_mode="HTML"
    )

# =========================================================
# CALLBACK — obuna tekshiruvi
# =========================================================

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def callback_check_sub(call):
    if check_sub(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # start() ni qayta chaqirish uchun fake message
        call.message.from_user = call.from_user
        start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)

# =========================================================
# HELPER
# =========================================================

def _save_qr_history(user_id, text):
    cursor.execute(
        "INSERT INTO qr_history(user_id, qr_text, created_date) VALUES(?,?,?)",
        (user_id, text, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()

# =========================================================
# UNKNOWN
# =========================================================

@bot.message_handler(func=lambda m: True)
def unknown(message):
    bot.send_message(
        message.chat.id,
        "❓ Noma'lum buyruq.\n\n/start — Bosh sahifa\n/panel — Admin panel"
    )

# =========================================================
# RUN
# =========================================================
bot.infinity_polling()