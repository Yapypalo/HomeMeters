import logging
import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from datetime import date

load_dotenv()
os.makedirs("data", exist_ok=True)
meter_label = {'cold': "Холодная вода🧊", 'hot': "Горячая вода🔥", 'light': "Свет💡"}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DEBUG_FLAG = os.getenv("DEBUG_FLAG")

def user_input_is_correct(message):
    if len(message) != 1:
        return False
    if not message[0].isdigit():
        return False
    return True

def load_data_for_date(date):
    with open('data/data.json', 'r', encoding='utf-8') as f:
            file_data = json.load(f)
    return file_data[date]

def write_data_to_json_file(data):
    today = date.today().isoformat() # сегодняшняя дата

    # проверяем что файл есть, если нет - созадём файл, если есть - открываем и читаем
    if not os.path.exists("data/data.json"):
        file_data = {}     
    else:
        with open('data/data.json', 'r', encoding='utf-8') as f:
            file_data = json.load(f)
    
    key, value = next(iter(data.items()))

    if today in file_data:
        file_data[today][key] = value
    else:
        file_data[today] = {key: value}

    # Записываем в файл значения
    with open('data/data.json', 'w', encoding='utf-8') as f:
        json.dump(file_data, f, indent=2, ensure_ascii=False)
            
async def handle_reading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_input = update.message.text.split(" ")
    cd = context.chat_data
    today = date.today().isoformat()

    if not user_input_is_correct(context.args):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Неверный формат. Используй одну из следующих команд:\n" +
                                       "/cold <значение> \n" +  
                                       "/hot <значение> \n" +
                                       "/light <значение>")
        return

    # 1) Запись в data.json
    m_type = user_input[0][1:]
    m_value = user_input[1]
    write_data_to_json_file({m_type: m_value})
    
    # 2) Инициализация сообщения-отчёта, если первый ввод за день
    if cd.get('report_date') != today:
        initial = f"{date.today().strftime('%d.%m.%Y')}\n\n" + \
                  "❌ Холодная вода🧊: --\n" + \
                  "❌ Горячая вода🔥: --\n" + \
                  "❌ Свет💡: --"
        msg = await context.bot.send_message(chat_id, initial)
        cd['report_date'] = today
        cd['report_msg_id'] = msg.message_id

    # 3) Считываем текущее состояние из data.json   
    day_data = load_data_for_date(today)

    # 4) Формируем строки для каждого счетчика
    lines = []
    for m in ('cold','hot','light'):
        if m in day_data:
            lines.append(f"✅ {meter_label[m]}: {day_data[m]}")
        else:
            lines.append(f"❌ {meter_label[m]}: --")
            
    # 5) Собираем полный текст и редактируем сообщение
    new_text = f"{date.today().strftime('%d.%m.%Y')}\n\n" + "\n".join(lines)
    await context.bot.edit_message_text(
        text=new_text,
        chat_id=chat_id,
        message_id=cd['report_msg_id']
    )

async def photo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    

    # 1) Определяем папку по дате
    today = date.today().isoformat() 
    dir_path = os.path.join("data/photos", today)
    os.makedirs(dir_path, exist_ok=True)
    
    # 2) Определяем количество файлов, если больше 3. То не даём больше загружать
    existing = os.listdir(dir_path)
    if len(existing) >= 3:
        await context.bot.send_message(chat_id, "ℹ️ Уже сохранено 3 фото сегодня.")
        return
    
    # 3) Получаем список фото-разрешений и выбираем самое большое
    photo_list = update.message.photo
    largest_photo = photo_list[-1]
    file = await largest_photo.get_file()

    # 4) Имя файла: можно использовать file.file_id + i.jpg
    filename = f"{file.file_id}.jpg"
    file_path = os.path.join(dir_path, filename)

    # 5) Сохраняем локально
    await file.download_to_drive(file_path)

    # 6) Ответ пользователю
    await context.bot.send_message(chat_id, f"✅ Фото сохранено: `{filename}`")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv("TOKEN")).build()
    
    start_handler = CommandHandler('start', start)
    commans_handler = CommandHandler(['cold', 'hot', 'light'], handle_reading)
    photo_handler = MessageHandler(filters.PHOTO, photo_save)
    
    application.add_handler(start_handler)
    application.add_handler(commans_handler)
    application.add_handler(photo_handler)
    
    application.run_polling()