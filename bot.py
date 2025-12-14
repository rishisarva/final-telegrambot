import os, csv, requests, asyncio
from io import StringIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BASE_URL = os.getenv("BASE_URL")
CSV_URL = "https://YOURDOMAIN.com/wp-content/uploads/telegram_stock.csv"
PORT = int(os.environ.get("PORT", 10000))


def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID


def load_csv():
    headers = {
        "User-Agent": "Mozilla/5.0 (TelegramBot)",
        "Accept": "text/csv,*/*"
    }

    r = requests.get(CSV_URL, headers=headers, timeout=15)
    r.raise_for_status()

    text = r.text.strip()

    if text.lower().startswith("<!doctype") or "<html" in text.lower():
        raise Exception("CSV URL returned HTML, not CSV")

    return list(csv.DictReader(StringIO(text)))



# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update):
        await update.message.reply_text("✅ Bot is running")


async def testcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rows = load_csv()
        if not rows:
            await update.message.reply_text("❌ CSV EMPTY")
            return

        headers = rows[0].keys()
        await update.message.reply_text(
            "CSV OK ✅\n\nColumns:\n" + ", ".join(headers)
        )
    except Exception as e:
        await update.message.reply_text(f"CSV ERROR ❌\n{e}")


async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()
    club_key = next((k for k in rows[0] if k.lower() == "club"), None)

    if not club_key:
        await update.message.reply_text("❌ No club column found")
        return

    clubs = sorted({r[club_key].strip() for r in rows if r.get(club_key)})

    keyboard = [[InlineKeyboardButton(c, callback_data=f"club|{c}")] for c in clubs]
    await update.message.reply_text(
        "🏷 Select Club",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    club = query.data.split("|")[1]
    rows = load_csv()
    products = [r for r in rows if r.get("club") == club][:5]

    for p in products:
        text = (
            f"📦 {p['title']}\n"
            f"💰 ₹{p['price']}\n"
            f"📏 Sizes: {p['sizes']}"
        )

        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Checkout", url=p["checkout_url"])]
        ])

        await query.message.reply_text(text, reply_markup=btn)


# ---------- APP ----------

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("testcsv", testcsv))
app.add_handler(CommandHandler("clubs", clubs))
app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))


if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{BASE_URL}/{BOT_TOKEN}",
    )
