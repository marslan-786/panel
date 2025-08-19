# ─────📦 Built-in Modules ─────
import os
import json
import random
import hashlib
from datetime import datetime, timedelta
from telegram.helpers import escape_markdown
import asyncio
import string


# ─────🌐 FastAPI ─────
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ─────🤖 Telegram Bot (Optional, Not Used Yet) ─────
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    Application,
)

# ─────🌀 Uvicorn ─────
import uvicorn

# ─────🚀 App Instance ─────
app = FastAPI()

# ─────🗂️ Configs ─────
DATA_FILE = "data/keys.json"
SECRET_KEY = "Vm8Lk7Uj2JmsjCPVPVjrLa7zgfx3uz9E"
OWNER_IDS = [8167904992, 8019937317]  # یہاں سب owner IDs رکھیں
OWNER_USERNAMES = ["@PubgQueen77", "@only_possible"]
PRIMARY_OWNER_ID = OWNER_IDS[0]  # For sending notifications and owner-only commands
ACCESS_FILE = "data/access.json"
BLOCKED_USERS_FILE = "data/blocked_users.json"

# ─────📂 Helper Functions ─────
def load_keys():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def generate_auth_token(user_key: str, uuid: str, secret_key: str):
    auth_string = f"PUBG-{user_key}-{uuid}-{secret_key}"
    return hashlib.md5(auth_string.encode()).hexdigest()

def find_key_owner(keys_data, user_key):
    for user_id, keys in keys_data.items():
        if user_key in keys:
            return user_id, keys[user_key]
    return None, None

def load_access_keys():
    if not os.path.exists(ACCESS_FILE):
        return {}
    with open(ACCESS_FILE, "r") as f:
        return json.load(f)

def save_access_keys(data):
    os.makedirs(os.path.dirname(ACCESS_FILE), exist_ok=True)
    with open(ACCESS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def delete_user_data(user_id):
    user_id = str(user_id)  # ensure string
    # Delete from license keys
    data = load_keys()
    if user_id in data:
        del data[user_id]
        save_keys(data)

    # Remove access keys owned by user
    access_data = load_access_keys()
    to_delete = [k for k, v in access_data.items() if str(v.get("owner")) == user_id]
    for k in to_delete:
        del access_data[k]
    save_access_keys(access_data)

    # Unblock if exists
    unblock_user_by_id(user_id)
    
def load_json(file_path):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except:
        return {}

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

def block_user_by_id(user_id: str):
    access_data = load_json(ACCESS_FILE)
    blocked_data = load_json(BLOCKED_USERS_FILE)

    # صرف وہ keys جو owner == user_id ہو
    keys_to_move = [key for key, val in access_data.items() if val.get("owner") == user_id]

    if not keys_to_move:
        return False  # user کا data access میں نہیں

    # صرف user کا data move کریں
    for key in keys_to_move:
        blocked_data[key] = access_data.pop(key)

    save_json(ACCESS_FILE, access_data)
    save_json(BLOCKED_USERS_FILE, blocked_data)
    return True

def unblock_user_by_id(user_id: str):
    access_data = load_json(ACCESS_FILE)
    blocked_data = load_json(BLOCKED_USERS_FILE)

    # صرف وہ keys جو owner == user_id ہو
    keys_to_move = [key for key, val in blocked_data.items() if val.get("owner") == user_id]

    if not keys_to_move:
        return False  # user کا data blocked میں نہیں

    # صرف user کا data move کریں
    for key in keys_to_move:
        access_data[key] = blocked_data.pop(key)

    save_json(ACCESS_FILE, access_data)
    save_json(BLOCKED_USERS_FILE, blocked_data)
    return True
    

def load_access():
    if os.path.exists(ACCESS_FILE):
        try:
            with open(ACCESS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def load_blocked_users():
    if os.path.exists(BLOCKED_USERS_FILE):
        try:
            with open(BLOCKED_USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

@app.api_route("/connect", methods=["GET", "POST"])
async def connect(request: Request):
    if request.method == "POST":
        form = await request.form()
        game = form.get("game")
        user_key = form.get("user_key")
        serial = form.get("serial")
    else:
        game = request.query_params.get("game")
        user_key = request.query_params.get("user_key")
        serial = request.query_params.get("serial")

    if not all([game, user_key, serial]):
        return JSONResponse({"status": False, "reason": "Missing Parameters"}, status_code=400)

    keys = load_keys()
    owner_id, key_data = find_key_owner(keys, user_key)

    if not key_data or not owner_id:
        return JSONResponse({"status": False, "reason": "Invalid or expired key"}, status_code=403)

    # ─── Skip checks if owner is in OWNER_IDS list ───
    if int(owner_id) not in OWNER_IDS:
        # ─── Check access.json ───
        access_ok = False
        if os.path.exists(ACCESS_FILE):
            try:
                with open(ACCESS_FILE, "r") as f:
                    access_data = json.load(f)
            except:
                access_data = {}

            all_expired = True  # assume sab expired hain

            for v in access_data.values():
                if isinstance(v, dict) and "devices" in v:
                    if str(owner_id) in v["devices"]:
                        access_expiry = v.get("expiry")
                        if access_expiry:
                            try:
                                expiry_dt = datetime.strptime(access_expiry, "%Y-%m-%d")
                                if expiry_dt >= datetime.now():
                                    access_ok = True
                                    all_expired = False
                                    break
                            except:
                                continue
                        else:
                            # expiry nahi likhi, assume valid
                            access_ok = True
                            all_expired = False
                            break

            if not access_ok and all_expired:
                return JSONResponse({
                    "status": False,
                    "reason": "Your access key is expired. Please contact your admin."
                }, status_code=403)

        # ─── Check blocked_users.json ───
        is_blocked = False
        if os.path.exists(BLOCKED_USERS_FILE):
            try:
                with open(BLOCKED_USERS_FILE, "r") as f:
                    blocked_data = json.load(f)
            except:
                blocked_data = {}

            for v in blocked_data.values():
                if isinstance(v, dict) and "devices" in v:
                    if str(owner_id) in v["devices"]:
                        is_blocked = True
                        break

        if is_blocked:
            return JSONResponse({
                "status": False,
                "reason": "Your admin is blocked by the panel owner. Please contact your admin."
            }, status_code=403)

        if not access_ok:
            return JSONResponse({"status": False, "reason": "Access denied. Invalid user."}, status_code=403)

    # ─── If key itself is blocked ───
    if key_data.get("blocked", False):
        return JSONResponse({"status": False, "reason": "Key is blocked"}, status_code=403)

    # ─── Check key expiry ───
    expiry_str = key_data.get("expiry", "")
    if expiry_str:
        expiry_date = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                expiry_date = datetime.strptime(expiry_str, fmt)
                break
            except:
                continue
        if not expiry_date:
            return JSONResponse({"status": False, "reason": "Invalid expiry format"}, status_code=500)

        if expiry_date < datetime.now():
            return JSONResponse({"status": False, "reason": "Key has expired"}, status_code=403)
    else:
        expiry_date = datetime.now() + timedelta(days=12)
        expiry_date = expiry_date.replace(hour=23, minute=59, second=59, microsecond=0)
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
        key_data["expiry"] = expiry_str
        keys[owner_id][user_key] = key_data
        save_keys(keys)

    # ─── Device Limit Check ───
    allowed_devices = key_data.get("max_devices", 1)
    connected_devices = key_data.get("devices", [])

    if serial not in connected_devices:
        max_dev = 9999 if allowed_devices in [-1, 9999] else allowed_devices
        if len(connected_devices) >= max_dev:
            return JSONResponse({"status": False, "reason": "Device limit reached"}, status_code=403)
        connected_devices.append(serial)
        key_data["devices"] = connected_devices
        keys[owner_id][user_key] = key_data
        save_keys(keys)

    # ─── Generate token ───
    token = generate_auth_token(user_key, serial, SECRET_KEY)
    rng = random.randint(1000000000, 1999999999)

    return JSONResponse({
        "status": True,
        "data": {
            "token": token,
            "rng": rng,
            "EXP": expiry_str
        }
    })
    
# ملٹیپل owners کے لیے

# ======== Bot Handlers ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    is_owner = user.id in OWNER_IDS or (user.username and user.username in OWNER_USERNAMES)

    access_keys = load_json(ACCESS_FILE)
    blocked_keys = load_json(BLOCKED_USERS_FILE)

    # ✅ Step 1: اگر user blocked ہے (یعنی اس کی ID blocked_keys میں کسی key کے اندر ہے)
    is_blocked = any(user_id in v.get("devices", []) for v in blocked_keys.values())

    if is_blocked:
        text = (
            "⛔ *Your access has been blocked by the owner.*\n\n"
            "To appeal or request unblocking, please contact the owner below 👇"
        )
        keyboard = [
            [InlineKeyboardButton("📞 Contact Owner", url=f"https://t.me/{OWNER_USERNAMES[0].lstrip('@')}")]
        ]

    # ✅ Step 2: اگر user allowed ہے (devices میں شامل ہے یا وہ owner ہے)
    elif any(user_id in v.get("devices", []) and not v.get("blocked", False) for v in access_keys.values()) or is_owner:
        text = (
            "🎉 *Welcome to Queen 👑 Panel!*😍\n\n"
            "✨ *You are a Premium Member!* 🥰\n"
            "🟢 Your membership is *Successfully activated* ✅.\n\n"
            f"👑 *Owner:* [{OWNER_USERNAMES[0]}](https://t.me/{OWNER_USERNAMES[0].lstrip('@')})\n\n"
            "💡 To use the panel features, simply click the buttons below 👇"
        )
        keyboard = [
            [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
            [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")],
            [InlineKeyboardButton("🔌 Connect URL", callback_data="connect_url")],
            [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAMES[0].lstrip('@')}")]
        ]
        if is_owner:
            keyboard.extend([
                [InlineKeyboardButton("🎫 Access Keys", callback_data="access_keys")],
                [InlineKeyboardButton("📂 Show My Access Keys", callback_data="show_my_access_keys")],
                [InlineKeyboardButton("📤 Backup Data", callback_data="backup_data")]
            ])

    # ✅ Step 3: اگر user new ہے (na devices میں, na blocked میں)
    else:
        text = (
            "🔐 *Welcome to Queen 👑 Panel!*\n\n"
            "🚫 You are not authorized yet.\n"
            "🎫 To get access, buy a key from 👇"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Buy Access Key", url=f"https://t.me/{OWNER_USERNAMES[0].lstrip('@')}")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.message:
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        else:
            await context.bot.send_message(
                chat_id=user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        print(f"✅ Sent start menu to user {user_id}")
    except Exception as e:
        print(f"❌ Error sending start message to {user_id}: {e}")

def generate_random_key(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
DEVICE_OPTIONS = [1, 2, 3, 5, 10, -1]  # -1 = Unlimited
DURATION_OPTIONS = ["1d", "3d", "7d", "15d", "30d", "1h", "6h"]

def parse_custom_key(text):
    parts = text.strip().split()
    if len(parts) < 1:
        return None
    key = parts[0]
    duration = 7  # default days
    devices = 1   # default devices

    for part in parts[1:]:
        if part.endswith("d"):
            try:
                duration = int(part[:-1])
            except:
                return None
        elif part.endswith("h"):
            try:
                # Convert hours to fraction of days
                duration = int(part[:-1]) / 24
            except:
                return None
        elif part.endswith("v"):
            try:
                devices = int(part[:-1])
            except:
                return None

    expiry_date = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")
    return key, int(devices), expiry_date

async def show_key_menu(query, context):
    idx_d = context.user_data.get("device_index", 0)
    idx_t = context.user_data.get("duration_index", 0)

    device_text = DEVICE_OPTIONS[idx_d]
    device_label = "Unlimited" if device_text == -1 else str(device_text)
    duration_text = DURATION_OPTIONS[idx_t]

    keyboard = [
        [InlineKeyboardButton(f"📱 Devices: {device_label}", callback_data="cycle_device")],
        [InlineKeyboardButton(f"⏱ Duration: {duration_text}", callback_data="cycle_duration")],
        [InlineKeyboardButton("🎲 Generate Random Key", callback_data="generate_random")],
        [InlineKeyboardButton("✏️ Add Your Custom Key", callback_data="add_custom")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🔐 *Generate a License Key:*\n\nCustomize the key below:",
        reply_markup=reply_markup, parse_mode="Markdown"
    )

async def save_key_and_reply(query, context, key):
    idx_d = context.user_data.get("device_index", 0)
    idx_t = context.user_data.get("duration_index", 0)

    device_count = DEVICE_OPTIONS[idx_d]
    if device_count == -1:
        device_count = 9999  # Unlimited devices

    duration = DURATION_OPTIONS[idx_t]
    now = datetime.now()

    # 🕒 Calculate expiry datetime
    if duration.endswith("h"):
        hours = int(duration[:-1])
        expiry_dt = now + timedelta(hours=hours)
    else:
        days = int(duration[:-1])
        expiry_dt = now + timedelta(days=days)
        expiry_dt = expiry_dt.replace(hour=23, minute=59, second=59, microsecond=0)  # 🔥 midnight expiry

    expiry = expiry_dt.strftime("%Y-%m-%d %H:%M:%S")

    user_id = str(query.from_user.id)
    data = load_keys()
    if user_id not in data:
        data[user_id] = {}

    data[user_id][key] = {
        "devices": [],
        "max_devices": device_count,
        "expiry": expiry,
        "blocked": False
    }
    save_keys(data)

    await query.edit_message_text(
        f"✅ Key `{key}` created for {device_count if device_count != 9999 else '∞'} device(s), valid till `{expiry}` \n\n🔁 Please send /start to refresh the panel.",
        parse_mode="Markdown"
    )

async def show_my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    data_json = load_keys()

    user_keys = data_json.get(user_id, {})
    if not user_keys:
        await query.edit_message_text("📂 You haven't generated any keys yet.")
        return

    keyboard = []
    for key, info in user_keys.items():
        used = len(info["devices"])
        maxd = info["max_devices"]
        exp = info["expiry"]
        blocked = info.get("blocked", False)
        stat = "🚫" if blocked else "✅"
        label = f"{stat} {key} | {exp} | {used}/{maxd if maxd != 9999 else '∞'} Devices"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"viewkey_{key}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📂 *Your License Keys:*", reply_markup=reply_markup, parse_mode="Markdown")

async def show_key_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    query = update.callback_query
    user_id = str(query.from_user.id)
    data_json = load_keys()

    key_data = data_json.get(user_id, {}).get(key)
    if not key_data:
        await query.edit_message_text("❌ Key not found.")
        return

    max_d = key_data["max_devices"]
    used_d = len(key_data["devices"])
    blocked = key_data.get("blocked", False)
    exp = key_data["expiry"]

    status = "🚫 Blocked" if blocked else "✅ Active"
    device_text = f"{used_d}/{max_d if max_d != 9999 else '∞'} Devices"

    keyboard = [
        [InlineKeyboardButton("➕ Add Time", callback_data=f"addtime_{key}"),
         InlineKeyboardButton("🔄 Reset Devices", callback_data=f"resetdev_{key}")],
        [InlineKeyboardButton("🚫 Unblock" if blocked else "🛑 Block", callback_data=f"toggle_{key}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{key}")],
        [InlineKeyboardButton("🔙 Back", callback_data="my_keys")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🔑 *{key}*\n\n⏳ *Expires:* {exp}\n📱 *Usage:* {device_text}\n📌 *Status:* {status}",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
ACCESS_DEVICE_OPTIONS = [1, 2, 3, 5, -1]
ACCESS_DURATION_OPTIONS = ["1d", "3d", "7d", "15d", "30d"]

async def show_access_key_menu(query, context):
    # اگر index موجود نہیں تو default 0 رکھو
    device_index = context.user_data.get("access_device_index", 0)
    duration_index = context.user_data.get("access_duration_index", 0)

    # label دکھانے کے لیے value نکالو
    device_label = ACCESS_DEVICE_OPTIONS[device_index]
    duration_label = ACCESS_DURATION_OPTIONS[duration_index]

    # اگر device -1 ہو تو ∞ دکھاؤ
    device_label = "∞" if device_label == -1 else device_label

    keyboard = [
        [InlineKeyboardButton(f"📱 Devices: {device_label}", callback_data="access_cycle_device")],
        [InlineKeyboardButton(f"⏱ Duration: {duration_label}", callback_data="access_cycle_duration")],
        [InlineKeyboardButton("🎲 Generate Access Key", callback_data="generate_access_random")],
        [InlineKeyboardButton("✏️ Add Custom Access Key", callback_data="add_custom_access")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎫 *Access Key Panel:*\n\nConfigure access keys:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
async def show_access_key_detail(query, context, key):
    try:
        access_data = load_access_keys()
        blocked_data = load_json(BLOCKED_USERS_FILE)

        key_data = access_data.get(key) or blocked_data.get(key)
        if not key_data:
            await query.answer("❌ Access key not found!")
            return

        maxd = key_data.get("max_devices", 0)
        usedd = len(key_data.get("devices", []))
        exp = key_data.get("expiry", "N/A")

        is_blocked = key in blocked_data
        status = "🚫 Blocked" if is_blocked else "✅ Active"

        keyboard = [
            [InlineKeyboardButton("🔓 Unblock" if is_blocked else "🛑 Block", callback_data=f"access_toggle_{key}")],
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"access_delete_{key}")],
            [InlineKeyboardButton("🔙 Back", callback_data="show_my_access_keys")]
        ]

        await query.edit_message_text(
            f"🎫 *{key}*\n\n📱 *Devices:* {usedd}/{maxd if maxd != 9999 else '∞'}\n⏳ *Expiry:* {exp}\n📌 *Status:* {status}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        print("⚠️ Error in show_access_key_detail():")
        print(e)
        await query.answer("❌ Error displaying details!")
    
async def show_my_access_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    access_data = load_access_keys()               # active keys
    blocked_data = load_json(BLOCKED_USERS_FILE)   # blocked keys

    # user کی active keys
    active_keys = {
        k: v for k, v in access_data.items()
        if str(v.get("owner")) == user_id or user_id in [str(d) for d in v.get("devices", [])]
    }

    # user کی blocked keys
    blocked_keys = {
        k: v for k, v in blocked_data.items()
        if str(v.get("owner")) == user_id or user_id in [str(d) for d in v.get("devices", [])]
    }

    if not active_keys and not blocked_keys:
        await query.edit_message_text("📂 You haven't generated or used any access keys yet.")
        return

    keyboard = []

    for key, info in active_keys.items():
        used = len(info.get("devices", []))
        maxd = info["max_devices"]
        exp = info["expiry"]
        label = f"✅ {key} | {exp} | {used}/{maxd if maxd != 9999 else '∞'} Devices"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"viewaccess_{key}")])

    for key, info in blocked_keys.items():
        used = len(info.get("devices", []))
        maxd = info["max_devices"]
        exp = info["expiry"]
        label = f"🚫 {key} | {exp} | {used}/{maxd if maxd != 9999 else '∞'} Devices"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"viewaccess_{key}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_main")])

    await query.edit_message_text(
        "📂 *Your Access Keys:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def unblock_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("❌ Only the owner can use this command!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unblockuser <user_id>")
        return

    user_id = context.args[0]
    unblock_user_by_id(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` has been unblocked.", parse_mode="Markdown")
    
async def block_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("❌ Only the owner can use this command!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /blockuser <user_id>")
        return

    user_id = context.args[0]
    block_user_by_id(user_id)
    await update.message.reply_text(f"🚫 User `{user_id}` has been blocked and all their keys are now inactive.", parse_mode="Markdown")


async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_IDS:
        await update.message.reply_text("❌ Only the owner can use this command!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /deleteuser <user_id>")
        return

    user_id = context.args[0]
    delete_user_data(user_id)
    await update.message.reply_text(f"🗑️ User `{user_id}` and all their data has been deleted.", parse_mode="Markdown")
    
async def save_access_key_and_reply(query, context, key):
    idx_d = context.user_data.get("access_device_index", 0)
    idx_t = context.user_data.get("access_duration_index", 0)

    device_count = ACCESS_DEVICE_OPTIONS[idx_d]
    if device_count == -1:
        device_count = 9999

    duration = ACCESS_DURATION_OPTIONS[idx_t]
    if duration.endswith("d"):
        expiry = (datetime.now() + timedelta(days=int(duration[:-1]))).strftime("%Y-%m-%d")
    else:
        expiry = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    access_data = load_access_keys()

    # ✅ owner ہمیشہ وہی ہو جو generate کر رہا ہے
    new_key_data = {
        "devices": [],
        "max_devices": device_count,
        "expiry": expiry,
        "blocked": False,
        "owner": str(query.from_user.id)  # owner کو کبھی نہ بدلیں
    }

    access_data[key] = new_key_data
    save_access_keys(access_data)

    await query.edit_message_text(
        f"✅ Access Key `{key}` created for {device_count if device_count != 9999 else '∞'} devices, valid till `{expiry}`.\n\n🔁 Please send /start to refresh the panel.",
        parse_mode="Markdown"
    )
    
# یہ آپ کی backup_data.py فائل ہے


# Configs جیسا کہ تم نے بتایا تھا
DATA_FILES = {
    "keys.json": "data/keys.json",
    "access.json": "data/access.json",
    "blocked_users.json": "data/blocked_users.json"
}

async def backup_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    await context.bot.send_message(chat_id=chat_id, text="📦 Backup شروع کیا جا رہا ہے...")

    for name, path in DATA_FILES.items():
        if os.path.exists(path):
            with open(path, "rb") as file:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=file,
                    filename=name,
                    caption=f"✅ `{name}` کا بیک اپ",
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ `{name}` فائل موجود نہیں ہے!",
                parse_mode="Markdown"
            )

    await context.bot.send_message(chat_id=chat_id, text="📁 Backup مکمل ہو گیا ✅ Please Again /start")

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()

    # ✅ Add Time to Key
    if user_data.get("awaiting_add_time_key"):
        key = user_data.pop("awaiting_add_time_key")
        keys = load_keys()

        if key in keys.get(user_id, {}):
            try:
                days_to_add = int(text)
                current_expiry = keys[user_id][key].get("expiry")
                if current_expiry:
                    expiry = datetime.strptime(current_expiry, "%Y-%m-%d")
                    new_expiry = expiry + timedelta(days=days_to_add)
                else:
                    new_expiry = datetime.now() + timedelta(days=days_to_add)

                keys[user_id][key]["expiry"] = new_expiry.strftime("%Y-%m-%d")
                save_keys(keys)
                await update.message.reply_text(
                    f"✅ Added {days_to_add} days to key `{key}`",
                    parse_mode="Markdown"
                )
                await show_key_detail(update, context, key)
                return
            except:
                await update.message.reply_text(
                    "⚠️ Please Again /start",
                    parse_mode="Markdown"
                )
                return
        else:
            await update.message.reply_text("❌ Key not found.")
            return

    # ✅ Custom License Key Handling
    if user_data.get("awaiting_custom_key"):
        user_data["awaiting_custom_key"] = False
        parsed = parse_custom_key(text)
        if not parsed:
            await update.message.reply_text(
                "❌ Invalid format. Use like:\n`MYKEY123 7d 2v`",
                parse_mode="Markdown"
            )
            return

        key, devices, expiry = parsed
        data = load_keys()
        if user_id not in data:
            data[user_id] = {}

        data[user_id][key] = {
            "devices": [],
            "max_devices": devices,
            "expiry": expiry,
            "blocked": False
        }
        save_keys(data)

        await update.message.reply_text(
            f"✅ Key `{key}` created for {devices if devices != 9999 else '∞'} device(s), valid till `{expiry}`\n\n🔁 Please send /start to refresh the panel.",
            parse_mode="Markdown"
        )
        return

    # ✅ Custom Access Key Handling
    if user_data.get("awaiting_custom_access_key"):
        user_data["awaiting_custom_access_key"] = False
        parsed = parse_custom_key(text)
        if not parsed:
            await update.message.reply_text(
                "❌ Invalid format. Use like:\n`ACCESSKEY 7d 2v`",
                parse_mode="Markdown"
            )
            return

        key, devices, expiry = parsed
        access_data = load_access_keys()
        access_data[key] = {
            "devices": [],
            "max_devices": devices,
            "expiry": expiry,
            "blocked": False,
            "owner": user_id
        }
        save_access_keys(access_data)

        await update.message.reply_text(
            f"✅ Access Key `{key}` created for {devices if devices != 9999 else '∞'} devices, valid till `{expiry}` \n\n🔁 Please send /start to refresh the panel.",
            parse_mode="Markdown"
        )
        return

    # ✅ Access Key Submission / Activation
    access_data = load_access_keys()
    key_data = access_data.get(text)

    if not key_data:
        await update.message.reply_text("❌ Invalid Access Key. Please check and try again. /start 🙂")
        return

    if key_data.get("blocked", False):
        await update.message.reply_text("🚫 This Access Key is blocked.")
        return

    expiry_str = key_data.get("expiry")
    if expiry_str:
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            if expiry_date < datetime.now():
                await update.message.reply_text("❌ This Access Key has expired.")
                return
        except:
            await update.message.reply_text("❌ Invalid expiry format. Please contact support.")
            return

    maxd = key_data.get("max_devices", 1)
    devices = key_data.get("devices", [])
    if user_id in devices:
        await update.message.reply_text("✅ You're already registered with this access key!")
        return
    elif len(devices) >= maxd and maxd != 9999:
        await update.message.reply_text("⚠️ Device limit reached for this access key.")
        return
    else:
        # ✅ Save user to access key
        devices.append(user_id)
        key_data["devices"] = devices
        access_data[text] = key_data
        save_access_keys(access_data)

        # ✅ Notify owner
        try:
            username = update.effective_user.username or "N/A"
            await context.bot.send_message(
                chat_id=PRIMARY_OWNER_ID,
                text=(
                    "🔔 *Access Key Used!*\n\n"
                    f"👤 User ID: `{user_id}`\n"
                    f"📛 Username: @{username}\n"
                    f"🔑 Access Key: `{text}`"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"❌ Failed to notify owner: {e}")
        return
        

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # access.json لوڈ کریں
    try:
        with open(ACCESS_FILE, "r") as f:
            access_data = json.load(f)
    except Exception as e:
        await update.message.reply_text("❌ Failed to load access.json")
        return

    # چیک کریں کہ user کسی entry کا owner ہے
    allowed = False
    target_devices = []

    for entry in access_data.values():
        if entry.get("owner") == user_id:
            allowed = True
            target_devices.extend(entry.get("devices", []))

    if not allowed and user_id not in [str(o) for o in OWNER_IDS]:
        await update.message.reply_text("⛔️ You are not authorized to use /send.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Please provide a message to send.\nUsage: /send Hello Everyone!")
        return

    message = " ".join(context.args)
    success = 0
    failed = 0

    for uid in set(target_devices):  # Remove duplicates
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            success += 1
        except Exception as e:
            failed += 1
            print(f"Failed to send to {uid}: {e}")

    await update.message.reply_text(f"✅ Message sent to {success} users.\n❌ Failed: {failed}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_data = context.user_data

    if data == "generate_key":
        user_data["device_index"] = 0
        user_data["duration_index"] = 0
        await show_key_menu(query, context)

    elif data == "cycle_device":
        user_data["device_index"] = (user_data.get("device_index", 0) + 1) % len(DEVICE_OPTIONS)
        await show_key_menu(query, context)

    elif data == "cycle_duration":
        user_data["duration_index"] = (user_data.get("duration_index", 0) + 1) % len(DURATION_OPTIONS)
        await show_key_menu(query, context)

    elif data == "generate_random":
        key = generate_random_key()
        await save_key_and_reply(query, context, key)

    elif data == "add_custom":
        await query.edit_message_text("✏️ Send your custom key like:\n`MYKEY123 7d 2v`", parse_mode="Markdown")
        user_data["awaiting_custom_key"] = True

    elif data == "my_keys":
        await show_my_keys(update, context)

    elif data.startswith("viewkey_"):
        _, key = data.split("_", 1)
        await show_key_detail(update, context, key)

    elif data.startswith("toggle_"):
        _, key = data.split("_", 1)
        user_id = str(query.from_user.id)
        data_json = load_keys()
        if key in data_json.get(user_id, {}):
            current = data_json[user_id][key].get("blocked", False)
            data_json[user_id][key]["blocked"] = not current
            save_keys(data_json)
            await query.answer("✅ Status updated")
            await show_key_detail(update, context, key)
        else:
            await query.answer("❌ Key not found")

    elif data.startswith("delete_"):
        _, key = data.split("_", 1)
        user_id = str(query.from_user.id)
        data_json = load_keys()
        if key in data_json.get(user_id, {}):
            del data_json[user_id][key]
            save_keys(data_json)
            await query.answer("🗑️ Key deleted")
            await show_my_keys(update, context)
        else:
            await query.answer("❌ Key not found")

    elif data.startswith("addtime_"):
        _, key = data.split("_", 1)
        context.user_data["awaiting_add_time_key"] = key
        await query.edit_message_text("🕒 Send number of days to add (e.g. `5`):", parse_mode="Markdown")

    elif data.startswith("resetdev_"):
        _, key = data.split("_", 1)
        user_id = str(query.from_user.id)
        keys = load_keys()
        if key in keys.get(user_id, {}):
            keys[user_id][key]["devices"] = []
            save_keys(keys)
            await query.answer("✅ Devices reset!")
            await show_key_detail(update, context, key)
        else:
            await query.answer("❌ Key not found")

    elif data == "back_main":
        user_id = str(query.from_user.id)
        is_owner = query.from_user.id in OWNER_IDS
        access_keys = load_access_keys()

        allowed = any(
            str(v.get("owner")) == user_id and not v.get("blocked", False)
            for v in access_keys.values()
        )

        text = (
            "🎉 *Welcome to Queen 👑 Panel!*😍\n\n"
            "✨ *You are a Premium Member!* 🥰\n"
            "🟢 Your membership is *Successfully activated* ✅.\n\n"
            f"👑 *Owner:* @PubgQueen77\n\n"
            "💡 To use the panel features, simply click the buttons below 👇"
        )
        text = escape_markdown(text, version=2)
        keyboard = [
            [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
            [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")],
            [InlineKeyboardButton("🔌 Connect URL", callback_data="connect_url")],
            [InlineKeyboardButton("👑 Owner", url=f"https://t.me/{OWNER_USERNAMES[0].lstrip('@')}")]
        ]

        if is_owner:
            keyboard.extend([
                [InlineKeyboardButton("🎫 Access Keys", callback_data="access_keys")],
                [InlineKeyboardButton("📂 Show My Access Keys", callback_data="show_my_access_keys")],
                [InlineKeyboardButton("📤 Backup Data", callback_data="backup_data")]
            ])

        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="MarkdownV2"
        )

    elif data == "connect_url":
        connect_url = "https://panels.impossible-world.xyz/connect"
        await query.edit_message_text(
            f"🔗 *Your Connect URL:*\n\n`{connect_url}`", parse_mode="Markdown"
        )

    elif data == "access_keys":
        if query.from_user.id not in OWNER_IDS:
            await query.answer("❌ Only owner can access this!", show_alert=True)
            return
        await show_access_key_menu(query, context)

    elif data == "show_my_access_keys":
        await show_my_access_keys(update, context)

    elif data.startswith("viewaccess_"):
        _, key = data.split("_", 1)
        await show_access_key_detail(query, context, key)

    elif data.startswith("access_toggle_"):
        try:
            key = data.replace("access_toggle_", "", 1)
            access_data = load_access_keys()
            blocked_data = load_json(BLOCKED_USERS_FILE)

            if key in access_data:
                user_id = str(access_data[key].get("owner"))
                success = block_user_by_id(user_id)
                if success:
                    await query.answer("🚫 User Blocked!")
                    await show_access_key_detail(query, context, key)
                else:
                    await query.answer("❌ Failed to block user.")
            elif key in blocked_data:
                user_id = str(blocked_data[key].get("owner"))
                success = unblock_user_by_id(user_id)
                if success:
                    await query.answer("🔓 User Unblocked!")
                    await show_access_key_detail(query, context, key)
                else:
                    await query.answer("❌ Failed to unblock user.")
            else:
                await query.answer("❌ Key not found.")
        except Exception as e:
            await query.answer("❌ Error occurred!")
            print(f"⚠️ Error in access_toggle_: {e}")

    elif data.startswith("access_delete_"):
        try:
            key = data.replace("access_delete_", "", 1)
            access_data = load_access_keys()
            if key in access_data:
                user_id = str(access_data[key].get("owner"))
                del access_data[key]
                save_access_keys(access_data)

                key_data = load_keys()
                if user_id in key_data:
                    del key_data[user_id]
                    save_keys(key_data)

                remaining = any(str(info.get("owner")) == user_id for info in access_data.values())
                if not remaining:
                    unblock_user_by_id(user_id)

                await query.answer("🗑️ Deleted")
                await show_my_access_keys(update, context)
            else:
                await query.answer("❌ Not found")
        except Exception as e:
            await query.answer("❌ Error occurred!")
            print("⚠️ Error in access_delete_:")

    elif data == "access_cycle_device":
        user_data["access_device_index"] = (user_data.get("access_device_index", 0) + 1) % len(ACCESS_DEVICE_OPTIONS)
        await show_access_key_menu(query, context)

    elif data == "access_cycle_duration":
        user_data["access_duration_index"] = (user_data.get("access_duration_index", 0) + 1) % len(ACCESS_DURATION_OPTIONS)
        await show_access_key_menu(query, context)

    elif data == "generate_access_random":
        key = generate_random_key()
        await save_access_key_and_reply(query, context, key)

    elif data == "add_custom_access":
        await query.edit_message_text("✏️ Send your custom access key like:\n`ACCESSKEY 7d 2v`", parse_mode="Markdown")
        user_data["awaiting_custom_access_key"] = True
                
    elif query.data == "backup_data":
        await backup_data_handler(update, context)

async def run_bot():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
    application.add_handler(CommandHandler("blockuser", block_user_command))
    application.add_handler(CommandHandler("unblockuser", unblock_user_command))
    application.add_handler(CommandHandler("deleteuser", delete_user_command))
    application.add_handler(CallbackQueryHandler(backup_data_handler, pattern="^backup_data$"))
    application.add_handler(CommandHandler("send", send))
    

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

async def run_api():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_api())

if __name__ == "__main__":
    asyncio.run(main())
