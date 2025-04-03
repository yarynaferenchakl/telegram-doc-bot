import logging
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()  # Дозволяє вкладати event loop


# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    logger.info(f"Отримано команду /start від chat_id: {chat_id}")
    await update.message.reply_text("Привіт від Hello World бота!")

async def main():
    # Замініть 'YOUR_TELEGRAM_TOKEN' на ваш реальний токен
    app = ApplicationBuilder().token("7744784753:AAEqhFaeR4LHx2PM0oHeYvwdUjB8tpwacd0").build()
    
    # Додаємо обробник для команди /start
    app.add_handler(CommandHandler("start", start_command))
    
    # Видаляємо вебхуки, якщо вони були встановлені
    await app.bot.delete_webhook()
    logger.info("Вебхуки видалені, запускаємо polling...")
    
    # Запускаємо бота у режимі polling
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
