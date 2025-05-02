from flask import Blueprint, request
from telegram import Update

# Create the Flask Blueprint
webhook = Blueprint("webhook", __name__)
application = None

# --- Initialization function to bind the Telegram app ---
def init_routes(app):
    """Initialize the routes with the Telegram application instance"""
    global application
    application = app

# --- Webhook endpoint for receiving Telegram updates ---
@webhook.route("/telegram", methods=["POST"])
def telegram_webhook():
    """Webhook endpoint for receiving updates from Telegram"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(), application.bot)
        application.loop.run_until_complete(
            application.process_update(update)
        )
    return "OK"

# --- Root endpoint to check bot status ---
@webhook.route("/")
def index():
    """Root endpoint to check if the bot is active"""
    return "Bot is up and running!"
