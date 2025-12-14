import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ===== ENV VARIABLES =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

WC_URL = "https://visionsjersey.com/wp-json/wc/v3/products"
WC_KEY = os.getenv("WC_KEY")
WC_SECRET = os.getenv("WC_SECRET")
# =========================

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return  # admin-only

    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Use:\n/search ronaldo")
        return

    r = requests.get(
        WC_URL,
        auth=(WC_KEY, WC_SECRET),
        params={"search": query, "per_page": 1}
    )

    products = r.json()
    if not products:
        await update.message.reply_text("❌ No product found")
        return

    p = products[0]

    title = p["name"]
    price = p["price"]
    link = p["permalink"]

    images = [img["src"] for img in p["images"]]

    sizes = []
    for attr in p["attributes"]:
        if attr["name"].lower() == "size":
            sizes = attr["options"]

    message = f"""📦 {title}

💰 Price: ₹{price}
📏 Sizes: {", ".join(sizes)}

🔗 {link}
"""

    # Send images (max 3)
    for img in images[:3]:
        await update.message.reply_photo(img)

    await update.message.reply_text(message)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("search", search))
app.run_polling()
