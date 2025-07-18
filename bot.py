# ─────📦 Built-in Modules ─────
import os
import json
import random
import hashlib
import traceback
from datetime import datetime, timedelta
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
OWNER_ID = 8003357608  # تمہارا Telegram user ID
OWNER_USERNAME = "@only_possible"  # تمہارا Telegram username
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

def load_blocked_users():
    if not os.path.exists(BLOCKED_USERS_FILE):
        return []
    with open(BLOCKED_USERS_FILE, "r") as f:
        return json.load(f)

def save_blocked_users(user_ids):
    os.makedirs(os.path.dirname(BLOCKED_USERS_FILE), exist_ok=True)
    with open(BLOCKED_USERS_FILE, "w") as f:
        json.dump(user_ids, f, indent=2)

def block_user_and_keys(user_id):
    user_id = str(user_id)  # ensure string
    # 1. Block user globally
    blocked = load_blocked_users()
    if user_id not in blocked:
        blocked.append(user_id)
        save_blocked_users(blocked)

    # 2. Block license keys
    data = load_keys()
    if user_id in data:
        for key in data[user_id]:
            data[user_id][key]["blocked"] = True
        save_keys(data)

    # 3. Block access keys
    access_data = load_access_keys()
    for key, info in access_data.items():
        if str(info.get("owner")) == user_id:
            access_data[key]["blocked"] = True
    save_access_keys(access_data)

def unblock_user(user_id):
    user_id = str(user_id)  # ensure string
    blocked = load_blocked_users()
    if user_id in blocked:
        blocked.remove(user_id)
        save_blocked_users(blocked)

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
    unblock_user(user_id)
    

        
# ─────🔌 /connect Endpoint ─────
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

    # اگر key یا owner نہ ملے تو انویلڈ
    if not key_data or not owner_id:
        return JSONResponse({"status": False, "reason": "Invalid or expired key"}, status_code=403)

    # چیک کریں کہ مالک بلاک ہے یا نہیں
    # فرض کریں مالک کی بلاک اسٹیٹس keys فائل کے اندر کسی بھی key کے ذریعے نہیں بلکہ آپ کسی الگ طریقے سے مینیج کرتے ہیں
    # ہم یہاں فرض کر لیتے ہیں کہ مالک بلاک ہے اگر keys میں مالک کے کسی بھی key پر blocked=True ہو (یا آپ الگ فائل استعمال کریں)
    owner_blocked = False
    for k, v in keys.get(owner_id, {}).items():
        if v.get("blocked", False):
            owner_blocked = True
            break

    if owner_blocked:
        # مالک بلاک ہے، تو موجودہ key کو بھی بلاک کر دو اگر نہیں بلاک ہے تو
        if not key_data.get("blocked", False):
            key_data["blocked"] = True
            keys[owner_id][user_key] = key_data
            save_keys(keys)

        return JSONResponse({"status": False, "reason": "User is blocked"}, status_code=403)

    # اگر key خود بلاک ہے
    if key_data.get("blocked", False):
        return JSONResponse({"status": False, "reason": "Key is blocked"}, status_code=403)

    # باقی expiry اور device limit چیک وہی رہیں گے
    expiry_str = key_data.get("expiry", "")
    if expiry_str:
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            if expiry_date < datetime.now():
                return JSONResponse({"status": False, "reason": "Key has expired"}, status_code=403)
        except Exception:
            return JSONResponse({"status": False, "reason": "Invalid expiry format"}, status_code=500)
    else:
        expiry_date = datetime.now() + timedelta(days=12)
        key_data["expiry"] = expiry_date.strftime("%Y-%m-%d")
        save_keys(keys)

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

    token = generate_auth_token(user_key, serial, SECRET_KEY)
    rng = random.randint(1000000000, 1999999999)

    return JSONResponse({
        "status": True,
        "data": {
            "token": token,
            "rng": rng
        }
    })


# ======== Bot Handlers ========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    is_owner = user.id == OWNER_ID
    access_keys = load_access_keys()

    # ڈیبگ: access_keys چیک کریں
    print("Access Keys Data:", access_keys)

    allowed = any(
        str(v.get("owner")) == user_id and not v.get("blocked", False)
        for v in access_keys.values()
    )

    # ڈیبگ: permissions چیک کریں
    print(f"User {user_id} | is_owner: {is_owner} | allowed: {allowed}")

    # میسج اور کی بورڈ تیار کریں
    if is_owner or allowed:
        text = (
            
                 "🎉 *Welcome to Impossible Panel!*😍\n\n"
                  "✨ *You are a Premium Member!* 🥰\n"
                  "🟢 Your membership is *Successfully activated* ✅.\n\n"
                  "👑 *Owner:* [@Only_Possible](https://t.me/Only_Possible)\n\n"
                  "💡 To use the panel features, simply click the buttons below 👇"
        )
        keyboard = [
            [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
            [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")],
            [InlineKeyboardButton("🔌 Connect URL", callback_data="connect_url")],
            [InlineKeyboardButton("👑 Owner", url="https://t.me/Only_Possible")]
        ]
        if is_owner:
            keyboard.extend([
                [InlineKeyboardButton("🎫 Access Keys", callback_data="access_keys")],
                [InlineKeyboardButton("📂 Show My Access Keys", callback_data="show_my_access_keys")]
            ])
    else:
        text = (
            "🔐 *Welcome to Impossible Panel!*\n\n"
            "🚫 You are not authorized yet.\n"
            "🎫 To get access, buy a key from @Only_Possible"
        )
        keyboard = [
            [InlineKeyboardButton("🛒 Buy Access Key", url="https://t.me/Only_Possible")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # میسج بھیجیں (پہلے update.message پر کوشش کریں، ورنہ context.bot سے)
    try:
        if update.message:
            await update.message.reply_text(
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
    except Exception as e:
        print(f"Failed to send message to {user_id}: {e}")

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
    if duration.endswith("h"):
        hours = int(duration[:-1])
        expiry = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d")
    else:
        days = int(duration[:-1])
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

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
        f"✅ Key `{key}` created for {device_count if device_count != 9999 else '∞'} device(s), valid till `{expiry}` Please Again /start",
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
        key_data = access_data.get(key)
        if not key_data:
            await query.answer("❌ Access key not found!")
            return

        maxd = key_data.get("max_devices", 0)
        usedd = len(key_data.get("devices", []))
        exp = key_data.get("expiry", "N/A")
        blocked = key_data.get("blocked", False)
        status = "🚫 Blocked" if blocked else "✅ Active"

        keyboard = [
            [InlineKeyboardButton("🚫 Unblock" if blocked else "🛑 Block", callback_data=f"access_toggle_{key}")],
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
        traceback.print_exc()
        await query.answer("❌ Error displaying details!")
    
async def show_my_access_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    access_data = load_access_keys()

    if not access_data:
        await query.edit_message_text("📂 You haven't generated any access keys yet.")
        return

    keyboard = []
    for key, info in access_data.items():
        used = len(info.get("devices", []))
        maxd = info["max_devices"]
        exp = info["expiry"]
        blocked = info.get("blocked", False)
        stat = "🚫" if blocked else "✅"
        label = f"{stat} {key} | {exp} | {used}/{maxd if maxd != 9999 else '∞'} Devices"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"viewaccess_{key}")])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="access_keys")])
    await query.edit_message_text("📂 *Your Access Keys:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
async def block_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can use this command!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /blockuser <user_id>")
        return

    user_id = context.args[0]
    block_user_and_keys(user_id)
    await update.message.reply_text(f"🚫 User `{user_id}` has been blocked and all their keys are now inactive.", parse_mode="Markdown")


async def unblock_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can use this command!")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unblockuser <user_id>")
        return

    user_id = context.args[0]
    unblock_user(user_id)
    await update.message.reply_text(f"✅ User `{user_id}` has been unblocked.", parse_mode="Markdown")


async def delete_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
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
    access_data[key] = {
        "devices": [],
        "max_devices": device_count,
        "expiry": expiry,
        "blocked": False,
        "owner": str(query.from_user.id)
    }
    save_access_keys(access_data)

    await query.edit_message_text(
        f"✅ Access Key `{key}` created for {device_count if device_count != 9999 else '∞'} devices, valid till `{expiry}` Please Again /start",
        parse_mode="Markdown"
    )
    
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
                return  # ✅ Success case: stop further processing
            except:
                await update.message.reply_text(
                    "⚠️ Please Again /start",
                    parse_mode="Markdown"
                )
                return  # ❌ Error case: stop further processing
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
            f"✅ Key `{key}` created for {devices if devices != 9999 else '∞'} device(s), valid till `{expiry}` Please Again /start",
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
            f"✅ Access Key `{key}` created for {devices if devices != 9999 else '∞'} devices, valid till `{expiry}` Please Again /start",
            parse_mode="Markdown"
        )
        return

    # ✅ Access Key Submission / Activation
    access_data = load_access_keys()
    key_data = access_data.get(text)

    if not key_data:
        await update.message.reply_text("❌ Invalid Access Key. Please check and try again.")
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
        devices.append(user_id)
        key_data["devices"] = devices
        key_data["owner"] = user_id
        access_data[text] = key_data
        save_access_keys(access_data)
        await update.message.reply_text("✅ Access granted! You can now use the panel. Use /start again.")
        return

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
        keyboard = [
            [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
            [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")],
            [InlineKeyboardButton("🔌 Connect URL", callback_data="connect_url")]
        ]
        if query.from_user.id == OWNER_ID:
            keyboard.append([InlineKeyboardButton("🎫 Access Keys", callback_data="access_keys")])
            keyboard.append([InlineKeyboardButton("📂 Show My Access Keys", callback_data="show_my_access_keys")])

        await query.edit_message_text(
            "🎉 *Welcome to Impossible Panel!*\n\nUse buttons below to manage your license keys:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "connect_url":
        connect_url = "https://panel-production-7db6.up.railway.app/connect"
        await query.edit_message_text(
            f"🔗 *Your Connect URL:*\n\n`{connect_url}`", parse_mode="Markdown"
        )

    elif data == "access_keys":
        if query.from_user.id != OWNER_ID:
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
            key = data[len("access_toggle_"):]
            access_data = load_access_keys()
            if key not in access_data:
                await query.answer("❌ Key not found")
                return

            current_status = access_data[key].get("blocked", False)
            access_data[key]["blocked"] = not current_status
            user_id = str(access_data[key].get("owner"))

            if not current_status:
                block_user_and_keys(user_id)
            else:
                unblock_user(user_id)

            save_access_keys(access_data)
            await query.answer("✅ Status Updated")
            await show_access_key_detail(query, context, key)

        except Exception as e:
            await query.answer("❌ Error occurred!")
            print(f"⚠️ Error in access_toggle_: {e}")
            traceback.print_exc()

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
                    unblock_user(user_id)

                await query.answer("🗑️ Deleted")
                await show_my_access_keys(update, context)
            else:
                await query.answer("❌ Not found")
        except Exception as e:
            await query.answer("❌ Error occurred!")
            print("⚠️ Error in access_delete_:")
            traceback.print_exc()

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

async def run_bot():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
    application.add_handler(CommandHandler("blockuser", block_user_command))
    application.add_handler(CommandHandler("unblockuser", unblock_user_command))
    application.add_handler(CommandHandler("deleteuser", delete_user_command))

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