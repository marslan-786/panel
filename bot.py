# ─────📦 Built-in Modules ─────
import os
import json
import random
import string
import hashlib
from datetime import datetime, timedelta
import asyncio

# ─────🌐 FastAPI ─────
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse

# ─────🤖 Telegram Bot ─────
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

# ─────🚀 FastAPI App Instance ─────
app = FastAPI()

# ─────🗂️ Constants ─────
DATA_FILE = "data/keys.json"
SECRET_KEY = "Vm8Lk7Uj2JmsjCPVPVjrLa7zgfx3uz9E"

# ─────📂 File Functions ─────
def load_keys():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ─────🔐 Token Generator ─────
def generate_auth_token(user_key: str, uuid: str, secret_key: str):
    auth_string = f"PUBG-{user_key}-{uuid}-{secret_key}"
    md5_hash = hashlib.md5(auth_string.encode()).hexdigest()
    return md5_hash

# ─────🌐 Main Connect API ─────
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

    # ✅ Validation
    if not all([game, user_key, serial]):
        return JSONResponse({"status": False, "reason": "Missing Parameters"}, status_code=400)

    # ✅ Load keys from JSON
    keys = load_keys()

    # ✅ Check if key exists
    if user_key not in keys:
        return JSONResponse({"status": False, "reason": "Invalid or expired key"}, status_code=403)

    # ✅ Check expiry
    expiry_str = keys[user_key].get("expiry", "")
    if expiry_str:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
        if expiry_date < datetime.now():
            return JSONResponse({"status": False, "reason": "Key has expired"}, status_code=403)

    # ✅ Check device limit
    allowed_devices = keys[user_key].get("device_limit", 1)
    connected_devices = keys[user_key].get("devices", [])

    if serial not in connected_devices:
        if len(connected_devices) >= allowed_devices:
            return JSONResponse({"status": False, "reason": "Device limit reached"}, status_code=403)
        else:
            connected_devices.append(serial)
            keys[user_key]["devices"] = connected_devices
            save_keys(keys)

    # ✅ Expiry Date (from key or fallback)
    exp_date = expiry_str if expiry_str else (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")

    # ✅ Token Generation
    token = generate_auth_token(user_key, serial, SECRET_KEY)

    # ✅ RNG
    rng = random.randint(100000, 999999)

    return JSONResponse({
        "status": True,
        "data": {
            "token": token,
            "rng": rng,
            "EXP": exp_date,
            "secret_key": SECRET_KEY
        }
    })


# ======== Bot Handlers ========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
        [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🎉 *Welcome to Impossible Panel!*\n\nUse buttons below to manage your license keys:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

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
        f"✅ Key `{key}` created for {device_count if device_count != 9999 else '∞'} device(s), valid till `{expiry}`",
        parse_mode="Markdown"
    )

async def handle_custom_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_custom_key"):
        context.user_data["awaiting_custom_key"] = False
        parsed = parse_custom_key(update.message.text)
        if not parsed:
            await update.message.reply_text(
                "❌ Invalid format. Use like:\n`MYKEY123 7d 2v` (Key Expiry DeviceCount)",
                parse_mode="Markdown"
            )
            return

        key, devices, expiry = parsed
        user_id = str(update.effective_user.id)
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
            f"✅ Key `{key}` created for {devices if devices != 9999 else '∞'} device(s), valid till `{expiry}`",
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

    elif data == "back_main":
        # Back to main menu
        keyboard = [
            [InlineKeyboardButton("🔐 Generate Key", callback_data="generate_key")],
            [InlineKeyboardButton("📂 My Keys", callback_data="my_keys")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎉 *Welcome to Impossible Panel!*\n\nUse buttons below to manage your license keys:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def run_bot():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_key))

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