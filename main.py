# =========================================================
#  MURODBEK PROFESSIONAL QR BOT  —  YANGI VERSIYA
#  0 dan qayta yozilgan  |  2025
# =========================================================

# =========================================================
#  CONFIG
# =========================================================
TOKEN            = "8608839152:AAF2BTh1h1ppv8J56ZX8Oy2vAkzr69gv7EY"
OWNER_ID         = 8133971943
DEFAULT_CHANNELS = ["@murodbek_rashidov"]
RATE_LIMIT_SEC   = 2

# =========================================================
#  IMPORTS
# =========================================================
import io
import os
import time
import sqlite3
from datetime import datetime

import qrcode
import telebot
from telebot import types
from PIL import Image
import cv2

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    PYZBAR_OK = True
except ImportError:
    PYZBAR_OK = False

# =========================================================
#  BOT
# =========================================================
bot = telebot.TeleBot(TOKEN)

# =========================================================
#  DATABASE
# =========================================================
conn   = sqlite3.connect("qrbot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    full_name   TEXT,
    phone       TEXT,
    username    TEXT,
    joined_date TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS qr_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER,
    qr_text      TEXT,
    created_date TEXT
);
CREATE TABLE IF NOT EXISTS banned_users (
    user_id     INTEGER PRIMARY KEY,
    reason      TEXT,
    banned_date TEXT
);
CREATE TABLE IF NOT EXISTS channels (
    channel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE
);
""")

for _ch in DEFAULT_CHANNELS:
    cursor.execute("INSERT OR IGNORE INTO channels(username) VALUES(?)", (_ch,))
conn.commit()

# =========================================================
#  HELPERS
# =========================================================

def get_channels() -> list:
    cursor.execute("SELECT username FROM channels")
    return [r[0] for r in cursor.fetchall()]

def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def is_admin(uid: int) -> bool:
    if is_owner(uid):
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,))
    return cursor.fetchone() is not None

def is_banned(uid: int) -> bool:
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id=?", (uid,))
    return cursor.fetchone() is not None

def is_registered(uid: int) -> bool:
    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))
    return cursor.fetchone() is not None

def save_qr_history(uid: int, text: str):
    cursor.execute(
        "INSERT INTO qr_history(user_id, qr_text, created_date) VALUES(?,?,?)",
        (uid, text, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()

# ─── Rate limit ───────────────────────────────────────────
_last: dict = {}

def rate_limited(uid: int) -> bool:
    now = time.time()
    if uid in _last and now - _last[uid] < RATE_LIMIT_SEC:
        return True
    _last[uid] = now
    return False

# ─── Guard ────────────────────────────────────────────────
def guard(msg) -> bool:
    uid = msg.from_user.id
    if is_banned(uid):
        bot.send_message(msg.chat.id, "🚫 Siz botdan bloklangansiz.")
        return False
    if rate_limited(uid):
        bot.send_message(msg.chat.id, "⏳ Iltimos biroz kuting (spam himoya).")
        return False
    return True

# ─── Subscription ─────────────────────────────────────────
def check_sub(uid: int) -> bool:
    for ch in get_channels():
        try:
            m = bot.get_chat_member(ch, uid)
            if m.status not in ("member", "administrator", "creator"):
                return False
        except Exception as e:
            print(f"[check_sub] {e}")
            return False
    return True

def sub_keyboard():
    kb = types.InlineKeyboardMarkup()
    for ch in get_channels():
        kb.add(types.InlineKeyboardButton(
            f"📢 {ch} — Obuna bo'lish",
            url=f"https://t.me/{ch.lstrip('@')}"
        ))
    kb.add(types.InlineKeyboardButton(
        "✅ Obuna bo'ldim — Tekshirish",
        callback_data="check_sub"
    ))
    return kb

# =========================================================
#  MENYULAR
# =========================================================

def show_main_menu(chat_id: int, uid: int):
    """Rol bo'yicha to'g'ri menyuni ko'rsatadi."""
    if is_owner(uid):
        _owner_panel(chat_id)
    elif is_admin(uid):
        _admin_panel(chat_id)
    else:
        _user_menu(chat_id)

def _user_menu(chat_id: int):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📷 QR Yaratish", "🎨 Rangli QR")
    kb.row("🖼 QR O'qish")
    kb.row("👤 Profil",       "📜 Tarix")
    kb.row("🗑 Tarixni Tozalash", "ℹ️ Bot Haqida")
    bot.send_message(chat_id, "🏠 <b>Asosiy Menyu</b>", reply_markup=kb, parse_mode="HTML")

def _admin_panel(chat_id: int):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("👥 Userlar",    "🔍 Qidirish")
    kb.row("📊 Statistika", "📤 Eksport")
    kb.row("📢 Broadcast",  "💬 Xabar Yuborish")
    kb.row("📷 QR Yaratish","🎨 Rangli QR")
    kb.row("🖼 QR O'qish",  "👤 Profil")
    kb.row("ℹ️ Bot Haqida")
    bot.send_message(chat_id, "🛠 <b>Admin Paneli</b>", reply_markup=kb, parse_mode="HTML")

def _owner_panel(chat_id: int):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("👥 Userlar",     "🔍 Qidirish")
    kb.row("📊 Statistika",  "📤 Eksport")
    kb.row("📢 Broadcast",   "💬 Xabar Yuborish")
    kb.row("🛡 Adminlar",    "➕ Admin Qo'sh",    "➖ Admin O'chir")
    kb.row("🔨 Ban",         "🔓 Unban",           "🚫 Banlist")
    kb.row("📡 Kanallar",    "➕ Kanal Qo'sh",    "➖ Kanal O'chir")
    kb.row("📷 QR Yaratish", "🎨 Rangli QR")
    kb.row("🖼 QR O'qish",   "👤 Profil")
    kb.row("ℹ️ Bot Haqida")
    bot.send_message(chat_id, "👑 <b>Ega Paneli</b>", reply_markup=kb, parse_mode="HTML")

# =========================================================
#  /start
# =========================================================

@bot.message_handler(commands=["start"])
def cmd_start(message):
    if not guard(message):
        return
    uid = message.from_user.id

    if not check_sub(uid):
        bot.send_message(
            message.chat.id,
            "👋 Xush kelibsiz!\n\n"
            "❗ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=sub_keyboard()
        )
        return

    if is_registered(uid):
        show_main_menu(message.chat.id, uid)
        return

    # Yangi foydalanuvchi — ro'yxatdan o'tkazish
    msg = bot.send_message(
        message.chat.id,
        "👋 Xush kelibsiz!\n\n👤 Ism Familiyangizni kiriting:"
    )
    bot.register_next_step_handler(msg, reg_get_name)

# /panel buyrug'i
@bot.message_handler(commands=["panel"])
def cmd_panel(message):
    if not is_admin(message.from_user.id):
        return
    show_main_menu(message.chat.id, message.from_user.id)

# =========================================================
#  RO'YXATDAN O'TISH
# =========================================================

def reg_get_name(message):
    full_name = message.text.strip() if message.text else ""
    if not full_name:
        msg = bot.send_message(message.chat.id, "❌ Ism bo'sh bo'lishi mumkin emas. Qayta kiriting:")
        bot.register_next_step_handler(msg, reg_get_name)
        return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 Telefon Raqam Yuborish", request_contact=True))
    msg = bot.send_message(
        message.chat.id,
        f"✅ Ism saqlandi: <b>{full_name}</b>\n\n📞 Telefon raqamingizni yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, lambda m: reg_save(m, full_name))

def reg_save(message, full_name):
    if not message.contact:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(types.KeyboardButton("📱 Telefon Raqam Yuborish", request_contact=True))
        msg = bot.send_message(
            message.chat.id,
            "❌ Iltimos tugma orqali telefon raqam yuboring:",
            reply_markup=kb
        )
        bot.register_next_step_handler(msg, lambda m: reg_save(m, full_name))
        return

    uid   = message.from_user.id
    phone = message.contact.phone_number
    uname = message.from_user.username
    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES(?,?,?,?,?)",
        (uid, full_name, phone, uname, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    bot.send_message(
        message.chat.id,
        "✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!",
        reply_markup=types.ReplyKeyboardRemove()
    )
    show_main_menu(message.chat.id, uid)

# =========================================================
#  QR — ODDIY
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📷 QR Yaratish")
def qr_create(message):
    if not guard(message):
        return
    msg = bot.send_message(message.chat.id, "✍️ Matn yoki link yuboring:")
    bot.register_next_step_handler(msg, qr_make)

def qr_make(message):
    if not message.text:
        bot.send_message(message.chat.id, "❌ Matn yuborilmadi.")
        return
    text = message.text
    qr   = qrcode.make(text)
    buf  = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    save_qr_history(message.from_user.id, text)
    bot.send_photo(message.chat.id, buf, caption="✅ QR Kod tayyor!")

# =========================================================
#  QR — RANGLI
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🎨 Rangli QR")
def qr_colored_menu(message):
    if not guard(message):
        return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔵 Ko'k",        callback_data="qrc_#1565C0"),
        types.InlineKeyboardButton("🔴 Qizil",       callback_data="qrc_#C62828"),
        types.InlineKeyboardButton("🟢 Yashil",      callback_data="qrc_#2E7D32"),
        types.InlineKeyboardButton("🟣 Binafsha",    callback_data="qrc_#6A1B9A"),
        types.InlineKeyboardButton("🟠 To'q sariq",  callback_data="qrc_#E65100"),
        types.InlineKeyboardButton("⚫ Qora",         callback_data="qrc_#000000"),
    )
    bot.send_message(message.chat.id, "🎨 Rang tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("qrc_"))
def qrc_selected(call):
    color = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"Rang: {color}")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    msg = bot.send_message(call.message.chat.id, "✍️ Matn yoki link yuboring:")
    bot.register_next_step_handler(msg, lambda m: qr_colored_make(m, color))

def qr_colored_make(message, fill_color):
    if not message.text:
        bot.send_message(message.chat.id, "❌ Matn yuborilmadi.")
        return
    text   = message.text
    qr_obj = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr_obj.add_data(text)
    qr_obj.make(fit=True)
    img = qr_obj.make_image(fill_color=fill_color, back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    save_qr_history(message.from_user.id, text)
    bot.send_photo(
        message.chat.id,
        buf,
        caption=f"✅ Rangli QR tayyor!\n🎨 Rang: <code>{fill_color}</code>",
        parse_mode="HTML"
    )

# =========================================================
#  QR — O'QISH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🖼 QR O'qish")
def qr_read_prompt(message):
    if not guard(message):
        return
    bot.send_message(message.chat.id, "🖼 QR kod rasmini yuboring:")

@bot.message_handler(content_types=["photo"])
def qr_decode(message):
    if not guard(message):
        return
    try:
        fi    = bot.get_file(message.photo[-1].file_id)
        data  = bot.download_file(fi.file_path)
        fname = f"{message.from_user.id}_qr.png"
        with open(fname, "wb") as f:
            f.write(data)

        result = None

        # 1-urinish: OpenCV
        img = cv2.imread(fname)
        det = cv2.QRCodeDetector()
        val, _, _ = det.detectAndDecode(img)
        if val:
            result = val

        # 2-urinish: pyzbar
        if not result and PYZBAR_OK:
            pil     = Image.open(fname)
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
            bot.send_message(message.chat.id, "❌ QR kod topilmadi. Aniqroq rasm yuboring.")

    except Exception as e:
        print(f"[qr_decode] {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi.")

# =========================================================
#  PROFIL
# =========================================================

@bot.message_handler(func=lambda m: m.text == "👤 Profil")
def profile(message):
    if not guard(message):
        return
    uid = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    u = cursor.fetchone()
    if not u:
        bot.send_message(message.chat.id, "❌ Profil topilmadi. /start bosing.")
        return
    cursor.execute("SELECT COUNT(*) FROM qr_history WHERE user_id=?", (uid,))
    qr_count = cursor.fetchone()[0]
    role = "👑 Ega" if is_owner(uid) else ("🛡 Admin" if is_admin(uid) else "👤 Foydalanuvchi")
    bot.send_message(
        message.chat.id,
        f"👤 <b>PROFIL</b>\n\n"
        f"📛 Ism: <b>{u[1]}</b>\n"
        f"📱 Telefon: <b>{u[2]}</b>\n"
        f"🔗 Username: @{u[3] or '—'}\n"
        f"🆔 ID: <code>{u[0]}</code>\n"
        f"📅 Sana: {u[4]}\n"
        f"🏷 Rol: {role}\n"
        f"📷 Jami QR: <b>{qr_count}</b> ta",
        parse_mode="HTML"
    )

# =========================================================
#  TARIX
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
#  TARIXNI TOZALASH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🗑 Tarixni Tozalash")
def clear_history_ask(message):
    if not guard(message):
        return
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Ha, o'chir",  callback_data="clr_yes"),
        types.InlineKeyboardButton("❌ Yo'q",        callback_data="clr_no")
    )
    bot.send_message(
        message.chat.id,
        "⚠️ Barcha QR tarixingiz o'chiriladi. Tasdiqlaysizmi?",
        reply_markup=kb
    )

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
#  BOT HAQIDA
# =========================================================

@bot.message_handler(func=lambda m: m.text == "ℹ️ Bot Haqida")
def about(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>PROFESSIONAL QR BOT</b>\n\n"
        "✅ QR yaratish (oddiy + rangli)\n"
        "✅ Rasm QR o'qish\n"
        "✅ Profil va tarix\n"
        "✅ Ega / Admin paneli\n"
        "✅ Dinamik kanal boshqaruvi\n"
        "✅ Ban / Unban tizimi\n"
        "✅ Broadcast\n"
        "✅ Spam himoya\n"
        "✅ Foydalanuvchi qidirish va eksport\n\n"
        "👨‍💻 Developer: <b>Murodbek</b>",
        parse_mode="HTML"
    )

# =========================================================
#  STATISTIKA
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
#  USERLAR RO'YXATI
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
#  QIDIRISH
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🔍 Qidirish")
def search_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🔍 ID yoki ism kiriting:")
    bot.register_next_step_handler(msg, search_user)

def search_user(message):
    q = message.text.strip() if message.text else ""
    if not q:
        bot.send_message(message.chat.id, "❌ Bo'sh qiymat.")
        return
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
        qn   = cursor.fetchone()[0]
        role = "👑 Ega" if is_owner(u[0]) else ("🛡 Admin" if is_admin(u[0]) else "👤 User")
        bot.send_message(
            message.chat.id,
            f"👤 <b>{u[1]}</b>\n"
            f"🆔 <code>{u[0]}</code>\n"
            f"📱 {u[2]}\n"
            f"🔗 @{u[3] or '—'}\n"
            f"📅 {u[4]}\n"
            f"🏷 {role}\n"
            f"📷 QR: <b>{qn}</b> ta",
            parse_mode="HTML"
        )

# =========================================================
#  EKSPORT
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
#  BROADCAST
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def broadcast_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(
        message.chat.id,
        "✍️ Reklama xabarini yuboring (matn, rasm+izoh yoki video):"
    )
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(message):
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
    bot.send_message(
        message.chat.id,
        f"✅ Yuborildi: <b>{ok}</b> / {len(all_u)}",
        parse_mode="HTML"
    )

# =========================================================
#  FOYDALANUVCHIGA XABAR
# =========================================================

@bot.message_handler(func=lambda m: m.text == "💬 Xabar Yuborish")
def msg_to_user_menu(message):
    if not is_admin(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Foydalanuvchi ID sini kiriting:")
    bot.register_next_step_handler(msg, msg_to_user_id)

def msg_to_user_id(message):
    if not message.text or not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    tid = int(message.text)
    msg = bot.send_message(message.chat.id, "✍️ Xabar matni:")
    bot.register_next_step_handler(msg, lambda m: msg_to_user_send(m, tid))

def msg_to_user_send(message, tid):
    try:
        bot.send_message(tid, f"📩 <b>Admin xabari:</b>\n\n{message.text}", parse_mode="HTML")
        bot.send_message(message.chat.id, "✅ Xabar yuborildi.")
    except Exception:
        bot.send_message(
            message.chat.id,
            "❌ Xabar yuborib bo'lmadi (user botni bloklagan bo'lishi mumkin)."
        )

# =========================================================
#  ADMINLAR  (faqat ega)
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

@bot.message_handler(func=lambda m: m.text == "➕ Admin Qo'sh")
def add_admin_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Yangi admin ID sini kiriting:")
    bot.register_next_step_handler(msg, add_admin_save)

def add_admin_save(message):
    if not message.text or not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    aid = int(message.text)
    cursor.execute("INSERT OR REPLACE INTO admins VALUES(?)", (aid,))
    conn.commit()
    bot.send_message(
        message.chat.id,
        f"✅ Admin qo'shildi: <code>{aid}</code>",
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "➖ Admin O'chir")
def del_admin_menu(message):
    if not is_owner(message.from_user.id):
        return
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ Admin mavjud emas.")
        return
    kb = types.InlineKeyboardMarkup()
    for (aid,) in rows:
        kb.add(types.InlineKeyboardButton(
            f"🗑 {aid} — O'chir",
            callback_data=f"deladm_{aid}"
        ))
    bot.send_message(message.chat.id, "🛡 O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("deladm_"))
def del_admin_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    aid = int(call.data.split("_", 1)[1])
    cursor.execute("DELETE FROM admins WHERE user_id=?", (aid,))
    conn.commit()
    bot.send_message(
        call.message.chat.id,
        f"✅ Admin o'chirildi: <code>{aid}</code>",
        parse_mode="HTML"
    )

# =========================================================
#  BAN / UNBAN / BANLIST  (faqat ega)
# =========================================================

@bot.message_handler(func=lambda m: m.text == "🔨 Ban")
def ban_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(message.chat.id, "🆔 Ban qilinadigan user ID:")
    bot.register_next_step_handler(msg, ban_get_id)

def ban_get_id(message):
    if not message.text or not message.text.isdigit():
        bot.send_message(message.chat.id, "❌ Noto'g'ri ID.")
        return
    tid = int(message.text)
    msg = bot.send_message(message.chat.id, "📝 Ban sababi:")
    bot.register_next_step_handler(msg, lambda m: ban_apply(m, tid))

def ban_apply(message, tid):
    reason = message.text or "Sabab ko'rsatilmagan"
    cursor.execute(
        "INSERT OR REPLACE INTO banned_users VALUES(?,?,?)",
        (tid, reason, datetime.now().strftime("%d.%m.%Y %H:%M"))
    )
    conn.commit()
    bot.send_message(
        message.chat.id,
        f"✅ <code>{tid}</code> bloklandi.\nSabab: {reason}",
        parse_mode="HTML"
    )
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
    kb = types.InlineKeyboardMarkup()
    for (uid, reason) in rows:
        kb.add(types.InlineKeyboardButton(
            f"🔓 {uid} — {reason[:20]}",
            callback_data=f"unban_{uid}"
        ))
    bot.send_message(message.chat.id, "🔓 Unban qilmoqchi bo'lgan userni tanlang:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("unban_"))
def unban_cb(call):
    bot.answer_callback_query(call.id)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    uid = int(call.data.split("_", 1)[1])
    cursor.execute("DELETE FROM banned_users WHERE user_id=?", (uid,))
    conn.commit()
    bot.send_message(
        call.message.chat.id,
        f"✅ <code>{uid}</code> unban qilindi.",
        parse_mode="HTML"
    )
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
#  KANAL BOSHQARUVI  (faqat ega)
# =========================================================

@bot.message_handler(func=lambda m: m.text == "📡 Kanallar")
def show_channels(message):
    if not is_owner(message.from_user.id):
        return
    channels = get_channels()
    if not channels:
        bot.send_message(message.chat.id, "❌ Hech qanday kanal yo'q.")
        return
    kb = types.InlineKeyboardMarkup()
    for ch in channels:
        kb.add(types.InlineKeyboardButton(
            f"📢 {ch}",
            url=f"https://t.me/{ch.lstrip('@')}"
        ))
    bot.send_message(
        message.chat.id,
        f"📡 <b>MAJBURIY OBUNA KANALLARI ({len(channels)} ta):</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@bot.message_handler(func=lambda m: m.text == "➕ Kanal Qo'sh")
def add_channel_menu(message):
    if not is_owner(message.from_user.id):
        return
    msg = bot.send_message(
        message.chat.id,
        "📡 Kanal username kiriting:\nMisol: <code>@kanalname</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, add_channel_save)

def add_channel_save(message):
    username = (message.text or "").strip()
    if not username.startswith("@"):
        username = "@" + username
    try:
        chat  = bot.get_chat(username)
        title = chat.title
    except Exception:
        bot.send_message(
            message.chat.id,
            "❌ Kanal topilmadi. Username to'g'ri ekanligini va bot kanalga admin sifatida qo'shilganligini tekshiring."
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
    kb = types.InlineKeyboardMarkup()
    for ch in channels:
        kb.add(types.InlineKeyboardButton(
            f"🗑 {ch} — O'chir",
            callback_data=f"delch_{ch}"
        ))
    bot.send_message(message.chat.id, "📡 O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=kb)

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
#  OBUNA TEKSHIRUVI  (callback)
# =========================================================

@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def cb_check_sub(call):
    if check_sub(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Tasdiqlandi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        call.message.from_user = call.from_user
        cmd_start(call.message)
    else:
        bot.answer_callback_query(
            call.id,
            "❌ Hali barcha kanallarga obuna bo'lmadingiz!",
            show_alert=True
        )

# =========================================================
#  NOMA'LUM XABAR
# =========================================================

@bot.message_handler(func=lambda m: True)
def unknown(message):
    bot.send_message(
        message.chat.id,
        "❓ Noma'lum buyruq.\n\n/start — Bosh sahifa\n/panel — Panel"
    )

# =========================================================
#  RUN
# =========================================================
bot.infinity_polling()