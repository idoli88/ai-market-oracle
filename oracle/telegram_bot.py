
import logging
from typing import List, Dict
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.constants import ParseMode
import asyncio

from oracle.config import settings
from oracle import database

logger = logging.getLogger(__name__)

class OracleBot:
    def __init__(self):
        self.app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self):
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("add", self.cmd_add))
        self.app.add_handler(CommandHandler("remove", self.cmd_remove))
        self.app.add_handler(CommandHandler("list", self.cmd_list))
        self.app.add_handler(CommandHandler("status", self.cmd_status))

    async def run(self):
        """Run the bot polling loop."""
        logger.info("Starting Telegram Bot polling...")
        # In a real production app with a scheduler loop, we might need a separate thread or process.
        # For MVP, we can run this alongside the scheduler if we manage the loop carefully.
        # But telegram's run_polling is blocking. 
        # We will use main.py to handle the scheduler, so the bot might need to run in a background task
        # or we just rely on webhooks. For simplicity here (MVP), polling is fine if main script handles it.
        await self.app.run_polling()

    # --- Commands ---

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        success = database.add_subscriber(chat_id)
        if success:
            await update.message.reply_text("ברוך הבא לאורקל! 🔮\nנרשמת בהצלחה.\nהשתמש בפקודה /add להוספת מניות.")
        else:
            await update.message.reply_text("שגיאה ברישום. נסה שוב מאוחר יותר.")

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
פקודות זמינות:
/add [TICKER] - הוספת מניה למעקב
/remove [TICKER] - הסרת מניה
/list - הצגת המניות שלך
/status - מצב המנוי
        """
        await update.message.reply_text(help_text)

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not context.args:
            await update.message.reply_text("אנא ציין סימול, למשל: /add NVDA")
            return
        
        ticker = context.args[0]
        success, msg = database.add_ticker_to_user(chat_id, ticker)
        await update.message.reply_text(msg)

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not context.args:
            await update.message.reply_text("אנא ציין סימול להסרה.")
            return

        ticker = context.args[0]
        success = database.remove_ticker_from_user(chat_id, ticker)
        if success:
            await update.message.reply_text(f"{ticker} הוסרה מהרשימה.")
        else:
            await update.message.reply_text("שגיאה בהסרה.")

    async def cmd_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        tickers = database.get_user_tickers(chat_id)
        if tickers:
            await update.message.reply_text(f"התיק שלך: {', '.join(tickers)}")
        else:
            await update.message.reply_text("התיק שלך ריק.")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        status = database.get_subscriber_status(chat_id)
        if status:
            await update.message.reply_text(f"מנוי פעיל עד: {status['subscription_end_date']}\nתוכנית: {status['plan']}")
        else:
            await update.message.reply_text("אינך רשום.")

    # --- Broadcast ---
    
    async def send_message_to_user(self, chat_id: int, message: str):
        try:
            # We need to use the bot instance directly for broadcast
            await self.app.bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

async def broadcast_report(active_users: List[Dict], reports: Dict[str, str]):
    """
    active_users: list of user dicts (chat_id, plan)
    reports: dict of ticker -> formatted report string
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    for user in active_users:
        chat_id = user["chat_id"]
        user_tickers = database.get_user_tickers(chat_id)
        
        # Build user-specific message
        msg_lines = [f"📊 *עדכון שוק*"]
        has_content = False
        
        for ticker in user_tickers:
            if ticker in reports:
                msg_lines.append(reports[ticker])
                msg_lines.append("---")
                has_content = True
        
        if not has_content:
            msg_lines.append("אין עדכונים מהותיים עבור המניות שלך כרגע.")
            
        final_msg = "\n".join(msg_lines)
        try:
            await bot.send_message(chat_id=chat_id, text=final_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Broadcast failed for {chat_id}: {e}")
