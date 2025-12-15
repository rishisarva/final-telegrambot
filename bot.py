import os, csv, requests, asyncio, random
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

PAGE_SIZE = 5
DELETE_AFTER = 300  # 5 minutes

# ---------- WEBHOOK CONFIG ----------
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # must be set in Render
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# ---------- MEMORY (avoid repeat in /daily9) ----------
USED_DAILY_IDS = set()

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


# 👉 FOR /clubs and /player ONLY
def club_player_text(p):
    return (
        f"🔥 {p['title']}\n\n"
        f"📏 Sizes: {p['sizes'].replace('|', ', ')}\n\n"
        f"📩 Want to order? Type \"YES\""
    )


# 👉 FOR /daily9 ONLY
def whatsapp_card_text(p):
    return (
        f"🔥 {p['title']}\n\n"
        f"📏 Sizes: {p['sizes'].replace('|', ', ')}\n"
        f"🔗 {p['link']}\n\n"
        f"⚡ Order fast — limited stock"
    )


async def auto_delete_messages(context, chat_id, message_ids):
    await asyncio.sleep(DELETE_AFTER)
    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id, mid)
        except:
            pass

# ---------- COMMANDS ----------

async def testcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = load_csv()
    first = rows[0]
    await update.message.reply_text(
        "CSV OK ✅\n\n"
        f"Columns:\n{', '.join(first.keys())}\n\n"
        f"Sample:\n{first['title']} | {first['club']}"
    )


async def clubs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    rows = load_csv()
    clubs = sorted(set(r["club"] for r in rows if r["club"]))

    buttons = [[InlineKeyboardButton(c, callback_data=f"club|{c}|0")] for c in clubs]

    await update.message.reply_text(
        "🏷 Select a Club",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def player_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚽ Usage: /player messi")
        return

    keyword = " ".join(context.args).lower()
    rows = load_csv()

    results = [r for r in rows if keyword in r["title"].lower()]
    if not results:
        await update.message.reply_text("❌ No jerseys found")
        return

    context.user_data["player_results"] = results
    await send_player_page(update, context, 0)

# ---------- DAILY 9 ----------

async def daily9(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    global USED_DAILY_IDS

    rows = load_csv()
    available = [r for r in rows if r["product_id"] not in USED_DAILY_IDS]

    if len(available) < 9:
        USED_DAILY_IDS.clear()
        available = rows

    random.shuffle(available)
    selected = available[:9]

    sent_ids = []

    for p in selected:
        USED_DAILY_IDS.add(p["product_id"])
        msg = await update.message.reply_photo(
            photo=p["image"],
            caption=whatsapp_card_text(p)
        )
        sent_ids.append(msg.message_id)

    asyncio.create_task(
        auto_delete_messages(context, update.message.chat_id, sent_ids)
    )

# ---------- CALLBACKS ----------

async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, club, page = query.data.split("|")
    page = int(page)

    rows = load_csv()
    products = [r for r in rows if r["club"] == club]

    await send_products_page(query.message, context, products, page)


async def send_products_page(message, context, products, page):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    total_pages = (len(products) + PAGE_SIZE - 1) // PAGE_SIZE

    sent_ids = []

    for p in products[start:end]:
        msg = await message.reply_photo(
            photo=p["image"],
            caption=club_player_text(p),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🛒 Checkout", callback_data=f"checkout|{p['product_id']}")
            ]])
        )
        sent_ids.append(msg.message_id)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page|{page-1}"))
    if end < len(products):
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page|{page+1}"))

    if nav:
        nav_msg = await message.reply_text(
            f"📄 Page {page+1}/{total_pages}",
            reply_markup=InlineKeyboardMarkup([nav])
        )
        sent_ids.append(nav_msg.message_id)

    asyncio.create_task(
        auto_delete_messages(context, message.chat_id, sent_ids)
    )


async def send_player_page(update, context, page):
    products = context.user_data["player_results"]
    await send_products_page(update.message, context, products, page)


async def page_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("|")[1])
    await send_player_page(query.message, context, page)


async def checkout_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = query.data.split("|")[1]
    rows = load_csv()
    product = next(r for r in rows if r["product_id"] == pid)

    size_map = dict(s.split(":") for s in product["variation_map"].split("|"))

    buttons = [
        [InlineKeyboardButton(size.upper(), callback_data=f"size|{pid}|{vid}")]
        for size, vid in size_map.items()
    ]

    msg = await query.message.reply_text(
        "📏 Select Size",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

    asyncio.create_task(
        auto_delete_messages(context, msg.chat_id, [msg.message_id])
    )


async def size_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, pid, vid = query.data.split("|")
    checkout_url = f"https://visionsjersey.com/checkout/?add-to-cart={pid}&variation_id={vid}"

    msg = await query.message.reply_text(
        "✅ Size selected\nProceed to checkout:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Checkout Now", url=checkout_url)
        ]])
    )

    asyncio.create_task(
        auto_delete_messages(context, msg.chat_id, [msg.message_id])
    )

# ---------- START BOT (WEBHOOK ONLY) ----------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("testcsv", testcsv))
    app.add_handler(CommandHandler("clubs", clubs))
    app.add_handler(CommandHandler("player", player_search))
    app.add_handler(CommandHandler("daily9", daily9))

    app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))
    app.add_handler(CallbackQueryHandler(page_click, pattern="^page\\|"))
    app.add_handler(CallbackQueryHandler(checkout_click, pattern="^checkout\\|"))
    app.add_handler(CallbackQueryHandler(size_click, pattern="^size\\|"))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL + WEBHOOK_PATH,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()