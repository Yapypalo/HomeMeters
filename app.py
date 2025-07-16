import logging
import os
import json
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from datetime import date

load_dotenv()
os.makedirs("data", exist_ok=True)

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
            


async def cold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_input_is_correct(context.args):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Неверный формат. Используй: \"/cold 123\"")
        return
    
    cold_value = int(context.args[0])
    write_data_to_json_file({"cold": cold_value})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Холодная вода: {cold_value}")
    


async def hot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_input_is_correct(context.args):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Неверный формат. Используй: \"/hot 123\"")
        return
    
    hot_value = int(context.args[0])
    write_data_to_json_file({"hot": hot_value})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Горячая вода: {hot_value}")

async def light(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not user_input_is_correct(context.args):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Неверный формат. Используй: \"/light 123\"")
        return
    
    light_value = int(context.args[0])
    write_data_to_json_file({"light": light_value})
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Свет: {light_value}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

if __name__ == '__main__':
    application = ApplicationBuilder().token(os.getenv("TOKEN")).build()
    
    start_handler = CommandHandler('start', start)
    cold_handler = CommandHandler('cold', cold, )
    hot_handler = CommandHandler('hot', hot)
    light_handler = CommandHandler('light', light)
    
    application.add_handler(start_handler)
    application.add_handler(cold_handler)
    application.add_handler(hot_handler)
    application.add_handler(light_handler)
    
    application.run_polling()