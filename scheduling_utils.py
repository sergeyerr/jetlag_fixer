import logging
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional
import os

from redis import Redis
from rq import Queue
from rq.registry import ScheduledJobRegistry
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

load_dotenv()

# Environment variables
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
TEST_SCHEDULED_MESSAGES = os.getenv("TEST_SCHEDULED_MESSAGES", "False").lower() in ("true", "1", "t")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedisConnectionSingleton:
    """Singleton class for Redis connection and job queue."""
    _instance: Optional['RedisConnectionSingleton'] = None
    _lock: Lock = Lock()

    def __new__(cls) -> 'RedisConnectionSingleton':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RedisConnectionSingleton, cls).__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.redis_conn: Redis = Redis(host=REDIS_HOST, port=REDIS_PORT)
        self.queue: Queue = Queue(connection=self.redis_conn)
        self.registry: ScheduledJobRegistry = ScheduledJobRegistry('default', connection=self.redis_conn)

    def get_redis_connection(self) -> Redis:
        return self.redis_conn

    def get_queue(self) -> Queue:
        return self.queue
    
    def get_registry(self) -> ScheduledJobRegistry:
        return self.registry


async def send_message_telegram(chat: int, msg: str) -> None:
    """
    Send a message via Telegram.
    """
    logger.info(f"Sending message to chat_id: {chat}")
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    await application.bot.send_message(chat_id=chat, text=msg)


def schedule_daily_reminder(message: str, flight_time: datetime, chat_id: int) -> None:
    """
    Schedule a daily reminder message until a specified datetime.
    """
    logger.info(f"Scheduling daily reminder: '{message}' for chat_id: {chat_id} at {flight_time}")
    queue = RedisConnectionSingleton().get_queue()
    
    if TEST_SCHEDULED_MESSAGES:
        schedule_message_telegram(queue, chat_id, message, 10)
    else:
        current_time = datetime.now()
        time_difference = flight_time - current_time
        seconds_in_a_day = 86400
        seconds_in_20_minutes = 1200
        days_to_send_message = int(time_difference.total_seconds() // seconds_in_a_day)
        time_to_12_00 = timedelta(hours=12) - timedelta(hours=current_time.hour, minutes=current_time.minute, seconds=current_time.second)
        
        for i in range(1, days_to_send_message):
            schedule_message_telegram(queue, chat_id, message, time_to_12_00.total_seconds() + i * seconds_in_a_day)
        
        schedule_message_telegram(queue, chat_id, message, time_difference.total_seconds() - seconds_in_20_minutes)
        
        
def delete_schedule_messages_for_user(registry: ScheduledJobRegistry, user_id: int) -> None:
    """
    Delete all scheduled messages for a specific user.
    """
    logger.info(f"Deleting scheduled messages for user_id: {user_id}")
    job_ids = registry.get_job_ids()
    queue = registry.get_queue()
    for job_id in job_ids:
        job = queue.fetch_job(job_id)
        if job.args[0] == user_id:
            job.cancel()
            logger.info(f"Deleted scheduled message with job_id: {job_id} for user_id: {user_id}")
            
            
def schedule_message_telegram(queue: Queue, user_id: int, message: str, seconds_delay: float) -> str:
    """
    Schedule a message to be sent via Telegram after a delay.
    """
    logger.info(f"Scheduling message '{message}' for user_id: {user_id} in {seconds_delay} seconds")
    job = queue.enqueue_in(timedelta(seconds=seconds_delay), send_message_telegram, user_id, message)
    return job.id


