import asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler
from pyngrok import ngrok
from telegram import Update
import logging

from src.application.telegram.config.settings import TELEGRAM_TOKEN, NGROK_TOKEN, WEBHOOK_PATH
from src.application.telegram.handlers.base_handlers import (
    start_handler, help_handler
)
from src.application.telegram.handlers.login_handlers import login_handler, logout_handler, register_handler
from src.application.telegram.routes.webhook_routes import webhook, init_routes
from src.application.telegram.handlers.plant_handlers import (
    update_plant_finish, update_plant_ask_field, update_plant_ask_value, update_plant_start,
    list_handler, create_plant2_start, create_plant2_ask_name, create_plant2_ask_city_and_io, create_plant2_ask_garden, ask_preset_handler,
    parse_city_and_io,create_plant2_finish, cancel_create_plant2,
    universal_fallback, delete_plant_handler, create_garden_handler, 
    list_gardens_handler, create_garden_handler, delete_garden_init, delete_garden_confirm, move_plant_handler, garden_info_handler,
    garden_status_handler, garden_analytics_handler
)
from src.application.telegram.handlers.command_handlers import calibrate_dry_handler, calibrate_wet_handler, water_handler, analytics_handler, status_handler
ASK_PLANT_NAME, ASK_FIELD, ASK_NEW_VALUE = range(3)
ASK_NEW_PLANT_ID, ASK_NEW_PLANT_NAME, ASK_CITY_AND_IO, ASK_GARDEN_SELECTION, ASK_AUTOWATER, ASK_PRESET = range(3,9)
ASK_GARDEN_CONFIRM=9
class TelegramWebhookHandler:
    def __init__(self, app):
        self.app = app
        self.application = None
        self.loop = None
        self.webhook_url = None

    def start(self):
        logging.info("[TelegramWebhook] Starting Telegram bot setup...")

        # Step 1: Event loop setup (required for Flask integration)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Step 2: Initialize bot
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.application.loop = self.loop
        self.app.config["TELEGRAM_BOT"] = self.application.bot


        # Step 3: Register command handlers
        self.setup_handlers()

        # Step 4: Start the bot (prepare webhook mode)
        self.loop.run_until_complete(self.application.initialize())
        self.loop.run_until_complete(self.application.start())

        # Step 5: Register Flask webhook routes
        init_routes(self.application)
        self.app.register_blueprint(webhook)

        # Step 6: Setup ngrok
        ngrok.set_auth_token(NGROK_TOKEN)
        public_url = ngrok.connect(5000).public_url
        self.webhook_url = f"{public_url}{WEBHOOK_PATH}"
        print(f"🚀 Telegram Webhook URL: {self.webhook_url}")

        # Step 7: Register webhook URL with Telegram
        self.loop.run_until_complete(
            self.application.bot.set_webhook(url=self.webhook_url)
        )
        self.application.telegram_loop = asyncio.new_event_loop()
        self.app.config["TELEGRAM_LOOP"] = self.application.telegram_loop
        import threading
        threading.Thread(target=self.application.telegram_loop.run_forever, daemon=True).start()
        print(f"🚀 Loop Telegram INSIDE attivo? {self.application.telegram_loop.is_running()}")

    def setup_handlers(self):
        conv_handler = ConversationHandler(
        entry_points=[CommandHandler("update_plant", update_plant_start)],
        states={
            ASK_PLANT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_plant_ask_field)],
            ASK_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_plant_ask_value)],
            ASK_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_plant_finish)],
        },
        fallbacks=[ CommandHandler("cancel", cancel_create_plant2),
                   MessageHandler(filters.COMMAND, universal_fallback)
                   ])

        create_plant2_conv = ConversationHandler(
            entry_points=[CommandHandler("create_plant", create_plant2_start)],
            states = {
            ASK_NEW_PLANT_ID:       [MessageHandler(filters.TEXT & ~filters.COMMAND, create_plant2_ask_name)],
            ASK_NEW_PLANT_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, create_plant2_ask_city_and_io)],
            ASK_CITY_AND_IO:        [MessageHandler(filters.TEXT & ~filters.COMMAND, parse_city_and_io)],
            ASK_GARDEN_SELECTION:   [MessageHandler(filters.TEXT & ~filters.COMMAND, create_plant2_ask_garden)],
            ASK_AUTOWATER:          [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_preset_handler)],
            ASK_PRESET:             [MessageHandler(filters.TEXT & ~filters.COMMAND, create_plant2_finish)],
            },
            fallbacks=[ 
                CommandHandler("cancel", cancel_create_plant2),
                MessageHandler(filters.COMMAND, universal_fallback),
            ]
        )
        
        delete_garden_conv = ConversationHandler(
        entry_points=[CommandHandler("delete_garden", delete_garden_init)],
        states={
            ASK_GARDEN_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, delete_garden_confirm)
            ]
        },
        fallbacks=[],
    )
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("analytics", analytics_handler))
        self.application.add_handler(CommandHandler("help", help_handler))
        self.application.add_handler(CommandHandler("login", login_handler))
        self.application.add_handler(CommandHandler("logout", logout_handler))
        self.application.add_handler(CommandHandler("register", register_handler))
        self.application.add_handler(CommandHandler("delete_plant", delete_plant_handler))
        self.application.add_handler(CommandHandler("listplants", list_handler))
        self.application.add_handler(CommandHandler("calibrate_dry", calibrate_dry_handler))
        self.application.add_handler(CommandHandler("calibrate_wet", calibrate_wet_handler))
        self.application.add_handler(CommandHandler("water", water_handler))
        self.application.add_handler(CommandHandler("status", status_handler))
        self.application.add_handler(conv_handler)
        self.application.add_handler(create_plant2_conv)
        self.application.add_handler(delete_garden_conv)
        self.application.add_handler(CommandHandler("create_garden", create_garden_handler))
        self.application.add_handler(CommandHandler("listgardens", list_gardens_handler))
        self.application.add_handler(CommandHandler("create_garden", create_garden_handler))
        self.application.add_handler(CommandHandler("moveplant", move_plant_handler))
        self.application.add_handler(CommandHandler("gardeninfo", garden_info_handler))
    def stop(self):
        logging.info("[TelegramWebhook] Stopping Telegram bot...")
        if self.application and self.loop:
            self.loop.run_until_complete(self.application.stop())
            self.loop.run_until_complete(self.application.shutdown())
            self.application.telegram_loop.stop()
            self.loop.close()



