import os, csv, requests, asyncio
from io import StringIO
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CSV_URL = "https://visionsjersey.com/wp-content/uploads/telegram_stock.csv"
DELETE_AFTER = 600  # 10 minutes


# ---------- DUMMY HTTP SERVER (RENDER FREE FIX) ----------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


# ---------- HELPERS ----------

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
    if "<html" in text.lower():
        raise Exception("CSV returned HTML, not CSV")

    return list(csv.DictReader(StringIO(text)))


async def auto_delete(context, chat_id, message_id):
    await asyncio.sleep(DELETE_AFTER)
    try:
        await context.bot.delete_message(chat_id, message_id)
    except:
        pass


# ---------- COMMANDS ----------

async def testcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = load_csv()
    first = rows[0]

    await update.message.reply_text(
        "CSV OK ✅\n\n"
        f"Columns:\n{', '.join(first.keys())}\n\n"
        f"Sample:\n"
        f"{first['title']} | {first['club']} | ₹{first['price']}"
    )


async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()
    clubs = sorted(set(r["club"] for r in rows if r["club"]))

    buttons = [
        [InlineKeyboardButton(c, callback_data=f"club|{c}")]
        for c in clubs
    ]

    await update.message.reply_text(
        "🏷 Select a Club",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------- CALLBACKS ----------

async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    club = query.data.split("|")[1]
    rows = load_csv()
    products = [r for r in rows if r["club"] == club][:5]

    for p in products:
        text = (
            f"📦 {p['title']}\n"
            f"💰 ₹{p['price']}\n"
            f"📏 Sizes: {p['sizes'].replace('|', ', ')}"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "🛒 Checkout",
                callback_data=f"checkout|{p['product_id']}"
            )
        ]])

        msg = await query.message.reply_photo(
            photo=p["image"],
            caption=text,
            reply_markup=keyboard
        )

        asyncio.create_task(
            auto_delete(context, msg.chat_id, msg.message_id)
        )


async def checkout_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = query.data.split("|")[1]
    rows = load_csv()
    product = next(r for r in rows if r["product_id"] == pid)

    size_map = dict(
        s.split(":") for s in product["variation_map"].split("|")
    )

    buttons = [
        [InlineKeyboardButton(
            size.upper(),
            callback_data=f"size|{pid}|{vid}"
        )]
        for size, vid in size_map.items()
    ]

    msg = await query.message.reply_text(
        "📏 Select Size",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    asyncio.create_task(
        auto_delete(context, msg.chat_id, msg.message_id)
    )


async def size_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pid, vid = query.data.split("|")

    checkout_url = (
        f"https://visionsjersey.com/checkout/"
        f"?add-to-cart={pid}&variation_id={vid}"
    )

    msg = await query.message.reply_text(
        "✅ Size selected\nProceed to checkout:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Checkout Now", url=checkout_url)
        ]])
    )

    asyncio.create_task(
        auto_delete(context, msg.chat_id, msg.message_id)
    )


# ---------- START BOT ----------

def main():
    # Start dummy HTTP server (Render free requirement)
    Thread(target=run_http_server, daemon=True).start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("testcsv", testcsv))
    app.add_handler(CommandHandler("clubs", clubs))
    app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))
    app.add_handler(CallbackQueryHandler(checkout_click, pattern="^checkout\\|"))
    app.add_handler(CallbackQueryHandler(size_click, pattern="^size\\|"))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

