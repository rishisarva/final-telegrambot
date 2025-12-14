import os, csv, requests, asyncio
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CSV_URL = "https://YOURDOMAIN.com/wp-content/uploads/telegram_stock.csv"
PORT = int(os.getenv("PORT", "10000"))

# Dummy web server for Render
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

def run_http():
    HTTPServer(("0.0.0.0", PORT), DummyHandler).serve_forever()

def is_admin(update):
    return update.effective_user.id == ADMIN_ID

def load_csv():
    r = requests.get(CSV_URL, timeout=10)
    r.raise_for_status()
    return list(csv.DictReader(StringIO(r.text)))

# /clubs command
async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()

    if not rows:
        await update.message.reply_text("CSV loaded but has no rows.")
        return

    headers = rows[0].keys()
    await update.message.reply_text(
        f"Detected columns:\n{', '.join(headers)}"
    )

    club_key = None
    for k in headers:
        if k.strip().lower() == "club":
            club_key = k
            break

    if not club_key:
        await update.message.reply_text("❌ No club column found.")
        return

    clubs = sorted(set(r.get(club_key, "").strip() for r in rows if r.get(club_key)))

    if not clubs:
        await update.message.reply_text("❌ Club column exists but is empty.")
        return

    buttons = [[InlineKeyboardButton(c, callback_data=f"club|{c}")] for c in clubs]

    await update.message.reply_text(
        "🏷 Select a Club",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# Club click
async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    club = query.data.split("|")[1]
    rows = load_csv()
    products = [r for r in rows if r["club"] == club][:5]

    for p in products:
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Checkout", callback_data=f"checkout|{p['product_id']}")
        ]])

        text = f"""📦 {p['title']}
💰 ₹{p['price']}
📏 Sizes: {p['sizes'].replace('|', ', ')}"""

        await query.message.reply_photo(p["image"])
        await query.message.reply_text(text, reply_markup=btn)

# Checkout click
async def checkout_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = query.data.split("|")[1]
    product = next(r for r in load_csv() if r["product_id"] == pid)

    size_map = dict(s.split(":") for s in product["variation_map"].split("|"))

    buttons = [[
        InlineKeyboardButton(size.upper(), callback_data=f"size|{pid}|{vid}")
    ] for size, vid in size_map.items()]

    msg = await query.message.reply_text(
        "📏 Select Size",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id))

# Size click
async def size_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pid, vid = query.data.split("|")
    checkout = f"https://YOURDOMAIN.com/checkout/?add-to-cart={pid}&variation_id={vid}"

    msg = await query.message.reply_text(
        "✅ Size selected\nProceed to checkout:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Checkout Now", url=checkout)
        ]])
    )

    asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id))

async def auto_delete(context, chat_id, msg_id):
    await asyncio.sleep(600)
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass

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
