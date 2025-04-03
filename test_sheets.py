import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Налаштування доступу до Google Sheets/Drive
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# Авторизація через файл credentials
creds = ServiceAccountCredentials.from_json_keyfile_name(
    "telegrambotsheets-455615-7de17c85df06.json", scope
)
client = gspread.authorize(creds)

# Відкриваємо таблицю та обираємо аркуш "зелена карта"
sheet = client.open("Маршрути Л_КОРП - 2023-2025").worksheet("зелена карта")

# Зчитуємо всі рядки таблиці
all_values = sheet.get_all_values()

# Заголовки – це другий рядок (індекс 1)
header = all_values[1]

# Дані – починаються з 4-го рядка (індекс 3)
data_rows = all_values[3:]

# Формуємо список словників: кожен рядок стає словником, де ключі – це заголовки
records = [dict(zip(header, row)) for row in data_rows]

# Виводимо отримані записи
for record in records:
    print(record)
