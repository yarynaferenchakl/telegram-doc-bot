import logging
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, CallbackContext
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Додаємо підтримку application_data через власний клас
class CustomContext(CallbackContext):
    @property
    def application_data(self):
        if not hasattr(self.application, '_shared_data'):
            self.application._shared_data = {}
        return self.application._shared_data

    @application_data.setter
    def application_data(self, value):
        self.application._shared_data = value

nest_asyncio.apply()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_cached_records = None
_cached_sheet = None
_cached_header = None

def get_records_cached():
    global _cached_records, _cached_sheet, _cached_header
    if _cached_records and _cached_sheet and _cached_header:
        return _cached_records, _cached_sheet, _cached_header

    import os
    import json
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Отримуємо JSON з env і перетворюємо у словник
    creds_json = os.environ["GOOGLE_CREDS_JSON"]
    creds_dict = json.loads(creds_json)

# Створюємо credentials з словника
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

    client = gspread.authorize(creds)
    sheet = client.open("Маршрути Л_КОРП - 2023-2025").worksheet("зелена карта")
    all_values = sheet.get_all_values()[:202]
    header = all_values[1]
    data_rows = all_values[3:]
    records = [dict(zip(header, row)) for row in data_rows if any(row)]

    _cached_records = records
    _cached_sheet = sheet
    _cached_header = header

    return records, sheet, header

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"Отримано команду /start від chat_id: {chat_id}")
    records, sheet, header = get_records_cached()
    user_records = [r for r in records if str(r.get("CHAT_ID_COLUMN", "")).strip() == str(chat_id)]

    if not user_records:
        await context.bot.send_message(chat_id=chat_id, text="Немає даних для відображення для вашого облікового запису.")
        return

    license_plates = sorted({record.get("Авто") for record in user_records if record.get("Авто")})
    if not license_plates:
        await context.bot.send_message(chat_id=chat_id, text="Немає номерних знаків для відображення.")
        return

    keyboard = [[InlineKeyboardButton(text=plate, callback_data=f"plate:{plate}")] for plate in license_plates]
    keyboard.append([InlineKeyboardButton("⬅️ Назад до головного меню", callback_data="go_home")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text("Оберіть номерний знак:", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text("Оберіть номерний знак:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    records, sheet, header = get_records_cached()

    if data.startswith("plate:"):
        plate = data.split(":", 1)[1]
        context.user_data['current_plate'] = plate
        doc_types = ["Зелена карта", "техогляд", "білий сертифікат", "митне свідоцтво", "легалізація тахографа", "автоцивілка"]
        keyboard = [[InlineKeyboardButton(text=doc, callback_data=f"doc:{plate}:{doc}")] for doc in doc_types]
        keyboard.append([InlineKeyboardButton("⬅️ Назад до авто", callback_data="back_to_plates")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад до головного меню", callback_data="go_home")])
        await query.edit_message_text(text=f"Ви обрали {plate}. Оберіть тип документа:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("doc:"):
        parts = data.split(":", 2)
        if len(parts) < 3:
            await query.edit_message_text(text="Невірний формат даних.")
            return
        plate = parts[1]
        doc_type = parts[2]
        context.user_data['current_plate'] = plate
        keyboard = [
            [InlineKeyboardButton("Переглянути дату документа", callback_data=f"view:{plate}:{doc_type}")],
            [InlineKeyboardButton("Оновити дату документа", callback_data=f"update:{plate}:{doc_type}")],
            [InlineKeyboardButton("⬅️ Назад до документів", callback_data=f"back_to_docs:{plate}")],
            [InlineKeyboardButton("⬅️ Назад до авто", callback_data="back_to_plates")]
        ]
        await query.edit_message_text(text=f"Ви обрали '{doc_type}' для {plate}. Що бажаєте зробити?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("view:"):
        plate = data.split(":", 2)[1]
        doc_type = data.split(":", 2)[2]
        record = next((r for r in records if r.get("Авто") == plate), None)
        if record:
            doc_date = record.get(doc_type, "невідомо")
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад до документа", callback_data=f"doc:{plate}:{doc_type}")],
                [InlineKeyboardButton("⬅️ Назад до авто", callback_data="back_to_plates")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=f"Дата документа '{doc_type}' для {plate}: {doc_date}",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(text=f"Запис для {plate} не знайдено.")

    elif data.startswith("update:"):
        plate = data.split(":", 2)[1]
        doc_type = data.split(":", 2)[2]
        context.user_data['update_plate'] = plate
        context.user_data['update_doc'] = doc_type
        context.user_data['current_plate'] = plate
        await query.edit_message_text(text=f"Введіть нову дату для '{doc_type}' для {plate} у форматі ДД.ММ.РРРР:")

    elif data == "open_start":
        logger.info("Натиснуто кнопку Старт")
        await start(update, context)

    elif data.startswith("back_to_docs:"):
        plate = data.split(":", 1)[1]
        doc_types = ["Зелена карта", "техогляд", "білий сертифікат", "митне свідоцтво", "легалізація тахографа", "автоцивілка"]
        keyboard = [[InlineKeyboardButton(text=doc, callback_data=f"doc:{plate}:{doc}")] for doc in doc_types]
        keyboard.append([InlineKeyboardButton("⬅️ Назад до авто", callback_data="back_to_plates")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад до головного меню", callback_data="go_home")])
        await query.edit_message_text(text=f"Ви обрали {plate}. Оберіть тип документа:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "back_to_plates":
        chat_id = query.message.chat.id
        user_records = [r for r in records if str(r.get("CHAT_ID_COLUMN", "")).strip() == str(chat_id)]
        license_plates = sorted({record.get("Авто") for record in user_records if record.get("Авто")})
        keyboard = [[InlineKeyboardButton(text=plate, callback_data=f"plate:{plate}")] for plate in license_plates]
        keyboard.append([InlineKeyboardButton("⬅️ Назад до головного меню", callback_data="go_home")])
        await query.edit_message_text(text="Оберіть номерний знак:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "go_home":
        await start(update, context)

    else:
        await query.edit_message_text(text="Невідомий запит.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'update_plate' in context.user_data and 'update_doc' in context.user_data:
        plate = context.user_data['update_plate']
        doc_type = context.user_data['update_doc']
        new_date = update.message.text.strip()
        records, sheet, header = get_records_cached()
        try:
            auto_index = header.index("Авто")
            doc_index = header.index(doc_type) + 1
        except ValueError:
            await update.message.reply_text("Помилка: не знайдено відповідного стовпця.")
            return

        updated = False
        for idx, record in enumerate(records, start=4):
            if record.get("Авто") == plate:
                sheet.update_cell(idx, doc_index, new_date)
                updated = True
                break

        if updated:
            keyboard = [
                [InlineKeyboardButton("⬅️ Назад до документа", callback_data=f"doc:{plate}:{doc_type}")],
                [InlineKeyboardButton("⬅️ Назад до головного меню", callback_data="go_home")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Дата для '{doc_type}' для {plate} оновлена на {new_date}.", reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"Не вдалося знайти запис для {plate}.")
        context.user_data.pop('update_plate', None)
        context.user_data.pop('update_doc', None)
    else:
        await update.message.reply_text("Невідоме повідомлення.")

async def main():
    try:
        application = ApplicationBuilder()\
            .token("7744784753:AAEqhFaeR4LHx2PM0oHeYvwdUjB8tpwacd0")\
            .context_types(ContextTypes(context=CustomContext))\
            .build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await application.bot.delete_webhook()
        logger.info("Вебхуки видалені, запускаємо polling...")
        await application.run_polling()
    except Exception as e:
        logger.error(f"❗ Помилка запуску бота: {e}")

if __name__ == '__main__':
    asyncio.run(main())
