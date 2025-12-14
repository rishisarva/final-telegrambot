import os
import csv
import requests
from io import StringIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== ENV =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CSV_URL = "https://YOURDOMAIN.com/wp-content/uploads/stock.csv"
# ===============

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

    # Limit to avoid spam
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

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("search", search))
app.run_polling()
