
import logging
from typing import List, Dict
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.constants import ParseMode
import asyncio

from oracle.config import settings
from oracle import database
from oracle.message_formatter import split_message

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
            chunks = split_message(message)
            for chunk in chunks:
                await self.app.bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

async def broadcast_report(active_users: List[Dict], reports: Dict[str, Dict], run_type: str = "normal"):
    """
    active_users: list of user dicts (chat_id, plan, notification_pref)
    reports: dict of ticker -> {'html': str, 'significant': bool}
    run_type: 'normal' | 'digest'
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    for user in active_users:
        chat_id = user["chat_id"]
        pref = user.get("notification_pref", "standard")
        user_tickers = database.get_user_tickers(chat_id)
        
        # Build user-specific message
        header_text = "סיכום יומי" if run_type == 'digest' else "עדכון שוק"
        msg_lines = [f"📊 <b>{header_text}</b>"]
        has_content = False
        
        for ticker in user_tickers:
            if ticker in reports:
                report_data = reports[ticker]
                is_significant = report_data['significant']
                report_html = report_data['html']
                
                should_send = False
                
                # Logic Matrix
                if pref == "3x_full":
                    should_send = True
                elif pref == "digest_only":
                    if run_type == "digest":
                        should_send = True
                elif pref == "alerts_only":
                    if is_significant:
                        should_send = True
                else: # standard
                    if run_type == "digest":
                        should_send = True
                    elif is_significant:
                        should_send = True
                
                if should_send:
                    msg_lines.append(report_html)
                    msg_lines.append("---")
                    has_content = True
        
        if has_content:
            final_msg = "\n".join(msg_lines)
            try:
                chunks = split_message(final_msg)
                for chunk in chunks:
                    await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.error(f"Broadcast failed for {chat_id}: {e}")
        # else: if no content (e.g. no alerts and standard mode), send nothing. Quiet is better.
