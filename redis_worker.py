from rq import Queue
from redis import Redis
import asyncio
import telegram
from telegram.ext import ApplicationBuilder

# TODO get it from env
tg_token = "6538724089:AAECebtmh57IKq9dvSdH-2I-sD2jNjzL7po"

# Connect to Redis server running in Docker
redis_conn = Redis(host='localhost', port=6379)
q = Queue(connection=redis_conn)


# Function to send a message via Telegram API
def send_message(chat_id, message):
    print(chat_id, message)

# using ApplicationBuilder
async def send_message_telegram(chat, msg):
    application = ApplicationBuilder().token(tg_token).build()
    await application.bot.sendMessage(chat_id=chat, text=msg)