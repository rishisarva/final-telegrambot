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

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

USED_DAILY_IDS = set()

# ---------- HELPERS ----------

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID


def load_csv():
    r = requests.get(
        CSV_URL,
        headers={"User-Agent": "TelegramBot"},
        timeout=15
    )
    r.raise_for_status()
    return list(csv.DictReader(StringIO(r.text)))


# 👉 /club & /player text
def club_player_text(p):
    return (
        f"🔥 {p['title']}\n\n"
        f"💰 Price: ₹{p['price']}\n"
        f"📏 Sizes: {p['sizes'].replace('|', ', ')}\n\n"
        f"📩 Want to order? Type \"YES\""
    )


# 👉 /daily9 text
def daily9_text(p):
    return (
        f"🔥 {p['title']}\n\n"
        f"📏 Sizes: {p['sizes'].replace('|', ', ')}\n"
        f"🔗 {p['link']}\n\n"
        f"⚡ Order fast — limited stock"
    )


async def auto_delete_messages(context, chat_id, ids):
    await asyncio.sleep(DELETE_AFTER)
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id, mid)
        except:
            pass

# ---------- COMMANDS ----------

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

    random.shuffle(results)
    context.user_data["products"] = results
    await send_products_page(update.message, context, 0)


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

    sent = []

    for p in selected:
        USED_DAILY_IDS.add(p["product_id"])
        msg = await update.message.reply_photo(
            photo=p["image"],
            caption=daily9_text(p)
        )
        sent.append(msg.message_id)

    asyncio.create_task(auto_delete_messages(context, update.message.chat_id, sent))


# ---------- CALLBACKS ----------

async def club_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, club, page = query.data.split("|")
    page = int(page)

    rows = load_csv()
    products = [r for r in rows if r["club"] == club]

    random.shuffle(products)
    context.user_data["products"] = products

    await send_products_page(query.message, context, page)


async def send_products_page(message, context, page):
    products = context.user_data["products"]

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    total_pages = (len(products) + PAGE_SIZE - 1) // PAGE_SIZE

    sent = []

    for p in products[start:end]:
        msg = await message.reply_photo(
            photo=p["image"],
            caption=club_player_text(p)
        )
        sent.append(msg.message_id)

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
        sent.append(nav_msg.message_id)

    asyncio.create_task(auto_delete_messages(context, message.chat_id, sent))


async def page_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("|")[1])
    await send_products_page(query.message, context, page)


# ---------- START BOT ----------

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("clubs", clubs))
    app.add_handler(CommandHandler("player", player_search))
    app.add_handler(CommandHandler("daily9", daily9))

    app.add_handler(CallbackQueryHandler(club_click, pattern="^club\\|"))
    app.add_handler(CallbackQueryHandler(page_click, pattern="^page\\|"))

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL + WEBHOOK_PATH,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()