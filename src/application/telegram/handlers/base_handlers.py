from telegram import Update
from telegram.ext import ContextTypes

# --- /start command handler ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command"""
    await update.message.reply_text(
        "Hello! I am the Smart Plant Bot, peak of electronic engineering evolution <3."
    )

# --- /help command handler ---
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /help command"""
    help_text = """
Available commands:
/start - Start the bot
/help  - Show this help message
/calc  - Calculate a simple expression (e.g., /calc 2 + 2)
"""
    await update.message.reply_text(help_text)

# --- Echo handler ---
async def echo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo handler that replies with the same message received"""
    await update.message.reply_text(update.message.text)



