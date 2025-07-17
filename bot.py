import asyncio
import json
import os
from datetime import datetime, timedelta
from fastapi import FastAPI
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    Application,
)
import uvicorn

# ======== CONFIG ========
DATA_FILE = "data/keys.json"
MAINTENANCE = False
app = FastAPI()

# ========= Load & Save =========
def load_keys():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_keys(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ========= API =========
@app.get("/connect")
async def connect(key: str, hwid: str):
    global MAINTENANCE
    if MAINTENANCE:
        return {"status": "error", "message": "Maintenance Mode"}

    data = load_keys()
    if key not in data:
        return {"status": "error", "message": "Invalid Key"}

    info = data[key]
    if datetime.strptime(info["expiry"], "%Y-%m-%d") < datetime.now():
        return {"status": "error", "message": "Key Expired"}

    if hwid not in info["devices"]:
        if len(info["devices"]) >= info["max_devices"]:
            return {"status": "error", "message": "Device Limit Reached"}
        info["devices"].append(hwid)
        save_keys(data)

    return {
        "status": "success",
        "token": f"{key}-{hwid}",
        "EXP": info["expiry"]
    }

# ========== BOT START ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

# ========== BUTTON HANDLER ==========
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "generate_key":
        await query.edit_message_text("🛠 Generating key...\n(Part 2 logic coming next...)")

    elif data == "my_keys":
        await query.edit_message_text("📂 Showing your keys...\n(Part 3 logic coming next...)")

# ========== RUN BOTH API & BOT ==========
async def run_bot():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    # Wait forever so bot doesn't stop
    await application.updater.idle()

async def run_api():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    await asyncio.gather(run_bot(), run_api())

if __name__ == "__main__":
    asyncio.run(main())