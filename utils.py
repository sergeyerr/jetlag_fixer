from redis import Redis, RedisError
from rq import Queue
from redis import Redis
from datetime import timedelta
from redis_worker import send_message, send_message_telegram
from rq.registry import ScheduledJobRegistry
import redis
from rq import Queue
from threading import Lock
import dotenv
from telegram.ext import ApplicationBuilder
import os
import pandas as pd
from datetime import datetime, timedelta

_ = dotenv.load_dotenv(dotenv.find_dotenv())

class RedisConnectionSingleton:
    # Usage
    # singleton_instance = RedisConnectionSingleton()
    # redis_conn = singleton_instance.get_redis_connection()
    # q = singleton_instance.get_queue()
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RedisConnectionSingleton, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.redis_conn = redis.Redis(host='localhost', port=6379)
        self.queue = Queue(connection=self.redis_conn)
        self.registry = ScheduledJobRegistry('default', connection=self.redis_conn)

    def get_redis_connection(self):
        return self.redis_conn

    def get_queue(self):
        return self.queue
    
    def get_registry(self):
        return self.registry
    
    
def schedule_daily_reminder(message: str, flight_time: datetime, chat_id: int):
    print(f"scheduling message: {message} to be sent at {flight_time} to chat_id: {chat_id}")
    # getting the test mode from the environment
    test_mode = os.getenv("TEST_SCHEDULED_MESSAGES", False)
    q = RedisConnectionSingleton().get_queue()
    
    if test_mode:
        # send the message only once after 10 seconds after the tool is called
        schedule_message_telegram(q, chat_id, message, 10)
    else:
        # schedule the message to be sent daily at 12:00 PM until the given datetime

        # get the current time
        current_time = datetime.now()
        # get the time difference between the current time and the flight time
        time_difference = flight_time - current_time
        # get the number of seconds in a day
        seconds_in_a_day = 86400
        # get the number of seconds in 20 minutes
        seconds_in_20_minutes = 1200
        # calculate the number of days to send the message
        days_to_send_message = time_difference.total_seconds() // seconds_in_a_day
        time_to_12_00 = timedelta(hours=12) - timedelta(hours=current_time.hour, minutes=current_time.minute, seconds=current_time.second)
        
        # schedule the message to be sent daily at 12:00 PM until the given datetime
        for i in range(1, int(days_to_send_message)):
            schedule_message_telegram(q, chat_id, message, time_to_12_00.total_seconds() + i * seconds_in_a_day)
            
        # schedule the last message to be sent 20 minutes before the specified datetime
        schedule_message_telegram(q, chat_id, message, time_difference.total_seconds() - seconds_in_20_minutes)


def get_pool_data():
    # URL of the Google Sheet
    sheet_url = os.getenv("POOL_URL")
    # Extract the CSV export URL from the Google Sheet URL
    csv_export_url = sheet_url.replace('/edit#gid=', '/export?format=csv&gid=')
    # Fetch the table data into a pandas DataFrame
    df = pd.read_csv(csv_export_url)
    return df


# 2 function with almost the same code for logical separation
def check_if_phone_number_exists(phone_number: int):
    df = get_pool_data()
    # Check if the phone number is in the DataFrame
    return phone_number in df.iloc[:, 1].values


def get_pool_info_by_phone_number(phone_number: int):
    df = get_pool_data()
    # Filter the DataFrame for the given phone number
    pool_info = df[df.iloc[:, 1] == phone_number]
    
    if len(pool_info) == 0:
        return None
    
    # Croping last 8 columns
    return pool_info.iloc[0, :-8].to_dict()

async def send_message_telegram(chat, msg):
    # get tg token from env
    tg_token = os.getenv("TELEGRAM_TOKEN")
    application = ApplicationBuilder().token(tg_token).build()
    await application.bot.sendMessage(chat_id=chat, text=msg)



def schedule_message_telegram(queue, user_id, message, seconds_delay):
    job = queue.enqueue_in(timedelta(seconds=seconds_delay), send_message_telegram, user_id, message)
    print(f"Scheduled message '{message}' for user {user_id} in {seconds_delay} seconds")
    return job.id



def delete_schedule_messages_for_user(registry, user_id):
    job_ids = registry.get_job_ids()
    queue = registry.get_queue()
    for job_id in job_ids:
        job = queue.fetch_job(job_id)
        job_data = job.args
        if job.args[0] == user_id:
            job.cancel()
            print(f"Deleted scheduled message for user {user_id}")
            


#check if queue is connected
def test_redis_connection(redis_conn):
    try:
        redis_conn.ping()
        print("Connected to Redis successfully!")
    except RedisError as e:
        print(f"Failed to connect to Redis: {e}")