import os, csv, requests, asyncio
from io import StringIO

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


# ---------- HELPERS ----------

def is_admin(update):
    return update.effective_user.id == ADMIN_ID


def load_csv():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv"
    }
    r = requests.get(CSV_URL, headers=headers, timeout=15)
    r.raise_for_status()

    text = r.text.strip()
    if "<html" in text.lower():
        raise Exception("CSV returned HTML")

    return list(csv.DictReader(StringIO(text)))


# ---------- DEBUG ----------

async def testcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    try:
        rows = load_csv()
        if not rows:
            await update.message.reply_text("❌ CSV loaded but EMPTY")
            return

        first = rows[0]
        await update.message.reply_text(
            "CSV OK ✅\n\n"
            f"Columns:\n{', '.join(first.keys())}\n\n"
            f"Sample:\n"
            f"Title: {first.get('title')}\n"
            f"Club: {first.get('club')}\n"
            f"Price: {first.get('price')}\n"
            f"Sizes: {first.get('sizes')}"
        )

    except Exception as e:
        await update.message.reply_text(f"CSV ERROR ❌\n{str(e)}")


# ---------- CLUB LIST ----------

async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()
    clubs = sorted({r["club"] for r in rows if r.get("club")})

    if not clubs:
        await update.message.reply_text("❌ No clubs found")
        return

    buttons = [
        [InlineKeyboardButton(c, callback_data=f"club|{c}")]
        for c in clubs
    ]

    await update.message.reply_text(
        "🏷 Select a Club",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------- CLUB CLICK ----------

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

        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🛒 Checkout", callback_data=f"checkout|{p['product_id']}")
        ]])

        await query.message.reply_photo(p["image"])
        await query.message.reply_text(text, reply_markup=btn)


# ---------- CHECKOUT ----------

async def checkout_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = query.data.split("|")[1]
    product = next(r for r in load_csv() if r["product_id"] == pid)

    size_map = dict(s.split(":") for s in product["variation_map"].split("|"))

    buttons = [
        [InlineKeyboardButton(size.upper(), callback_data=f"size|{pid}|{vid}")]
        for size, vid in size_map.items()
    ]

    msg = await query.message.reply_text(
        "📏 Select Size",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    asyncio.create_task(auto_delete(context, msg.chat_id, msg.message_id))


# ---------- SIZE ----------

async def size_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pid, vid = query.data.split("|")
    checkout = f"https://visionsjersey.com/checkout/?add-to-cart={pid}&variation_id={vid}"

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


# ---------- RUN ----------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("testcsv", testcsv))
    app.add_handler(CommandHandler("clubs", clubs))
    app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))
    app.add_handler(CallbackQueryHandler(checkout_click, pattern="^checkout\\|"))
    app.add_handler(CallbackQueryHandler(size_click, pattern="^size\\|"))

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
