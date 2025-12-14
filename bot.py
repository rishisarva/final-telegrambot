import os
import csv
import requests
import asyncio
from io import StringIO
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

# =====================
# ENV
# =====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CSV_URL = "https://visionsjersey.com/wp-content/uploads/telegram_stock.csv"
PORT = int(os.getenv("PORT", "10000"))

# =====================
# DUMMY HTTP SERVER
# =====================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_http():
    HTTPServer(("0.0.0.0", PORT), DummyHandler).serve_forever()

# =====================
# HELPERS
# =====================
def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

def load_csv():
    r = requests.get(CSV_URL, timeout=10)
    r.raise_for_status()
    return list(csv.DictReader(StringIO(r.text)))

def get_unique_clubs(rows):
    return sorted(set(r["club"] for r in rows if r["club"]))

# =====================
# COMMAND: /clubs
# =====================
async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()
    clubs = get_unique_clubs(rows)

    buttons = [
        [InlineKeyboardButton(c, callback_data=f"club|{c}")]
        for c in clubs
    ]

    await update.message.reply_text(
        "🏷 Select a Club",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# =====================
# CLUB CLICK
# =====================
async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    club = query.data.split("|", 1)[1]
    rows = load_csv()

    products = [r for r in rows if r["club"] == club][:5]

    for p in products:
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🛒 Checkout",
                callback_data=f"checkout|{p['product_id']}"
            )]
        ])

        text = (
            f"📦 {p['title']}\n"
            f"💰 ₹{p['price']}\n"
            f"📏 Sizes: {p['sizes'].replace('|', ', ')}"
        )

        await query.message.reply_photo(p["image"])
        await query.message.reply_text(text, reply_markup=btn)

# =====================
# CHECKOUT CLICK
# =====================
async def checkout_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = query.data.split("|")[1]
    rows = load_csv()
    product = next(r for r in rows if r["product_id"] == product_id)

    size_map = dict(
        s.split(":") for s in product["variation_map"].split("|")
    )

    buttons = [
        [InlineKeyboardButton(size.upper(),
         callback_data=f"size|{product_id}|{size}|{vid}")]
        for size, vid in size_map.items()
    ]

    msg = await query.message.reply_text(
        "📏 Select Size",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id))

# =====================
# SIZE CLICK
# =====================
async def size_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pid, size, vid = query.data.split("|")

    checkout_url = (
        f"https://YOURDOMAIN.com/checkout/"
        f"?add-to-cart={pid}&variation_id={vid}"
    )

    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Checkout Now", url=checkout_url)]
    ])

    msg = await query.message.reply_text(
        f"🧾 Size **{size.upper()}** selected\nProceed to checkout:",
        reply_markup=btn,
        parse_mode="Markdown"
    )

    asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id))

# =====================
# AUTO DELETE
# =====================
async def auto_delete(context, chat_id, msg_id):
    await asyncio.sleep(600)
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass

# =====================
# MAIN
# =====================
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("clubs", clubs))
    app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))
    app.add_handler(CallbackQueryHandler(checkout_click, pattern="^checkout\\|"))
    app.add_handler(CallbackQueryHandler(size_click, pattern="^size\\|"))

    app.run_polling()

if __name__ == "__main__":
    Thread(target=run_http, daemon=True).start()
    run_bot()
