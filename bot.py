import os
import csv
import requests
from io import StringIO
from threading import Thread

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from flask import Flask

# =====================
# ENV
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CSV_URL = "https://YOURDOMAIN.com/wp-content/uploads/stock.csv"
PORT = int(os.getenv("PORT", 10000))

# =====================
# FLASK DUMMY SERVER
# =====================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "Bot is running"

def run_flask():
    app_flask.run(host="0.0.0.0", port=PORT)

# =====================
# TELEGRAM BOT
# =====================
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

def load_csv():
    r = requests.get(CSV_URL, timeout=10)
    r.raise_for_status()
    return list(csv.DictReader(StringIO(r.text)))

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    query = " ".join(context.args).strip().lower()
    if not query:
        await update.message.reply_text("Use:\n/search barcelona")
        return

    products = load_csv()
    matches = [
        p for p in products
        if p["club"] and query in p["club"].lower()
    ]

    if not matches:
        await update.message.reply_text("❌ No in-stock jerseys found for this club")
        return

    for p in matches[:5]:
        sizes = p["sizes"].replace("|", ", ")

        text = f"""📦 {p["title"]}

🏷 Club: {p["club"]}
💰 Price: ₹{p["price"]}
📏 Sizes: {sizes}

🔗 {p["link"]}
"""

        await update.message.reply_photo(p["image"])
        await update.message.reply_text(text)

def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("search", search))
    app.run_polling()

# =====================
# START BOTH
# =====================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    run_bot()
