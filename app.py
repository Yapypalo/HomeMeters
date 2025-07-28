import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, ConversationHandler, MessageHandler, filters
import os
from commands import conv_handler, handle_photos

load_dotenv()
logging.basicConfig(level=logging.INFO)

def main():
    token = os.getenv('TOKEN')
    app = ApplicationBuilder().token(token).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photos))
    app.add_handler(conv_handler)
    app.run_polling()

if __name__=='__main__':
    main()
