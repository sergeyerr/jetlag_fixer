import os
import logging
import nest_asyncio
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, ApplicationBuilder, CallbackContext, filters
from langgraph.checkpoint.sqlite import SqliteSaver
from auth_graph import AuthGraph
from recommendation_graph import RecommendationGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai.chat_models.base import ChatOpenAI
from scheduling_utils import delete_schedule_messages_for_user, RedisConnectionSingleton
from langgraph_utils import get_answer_for_auth_graph, reset_auth_graph, get_answer_for_recommendation_graph

# Load environment variables
tg_token = os.environ.get('TELEGRAM_TOKEN')

# Initialize in-memory SQLite database for checkpointing
memory = SqliteSaver.from_conn_string(":memory:")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_state(user_id: int) -> None:
    """
    Reset the authentication graph and clears scheduler messages  for a user.
    """
    redis_registry = RedisConnectionSingleton().get_registry()
    delete_schedule_messages_for_user(redis_registry, user_id)
    
    agent = AuthGraph(memory)
    thread_config = {"configurable": {"thread_id": user_id}}
    response = reset_auth_graph(agent, thread_config)
    return response

async def start(update: Update, context: CallbackContext) -> None:
    """
    Handle the /start command. Initialize the authentication graph and provide the initial response.
    """
    logger.info("Received /start command")
    response = reset_state(update.message.from_user.id)
    await update.message.reply_text(response)

async def clear(update: Update, context: CallbackContext) -> None:
    """
    Handle the /clear command. Delete scheduled messages and reset the authentication graph.
    """
    logger.info("Received /start command")
    response = reset_state(update.message.from_user.id)
    await update.message.reply_text(response)

async def handle_message(update: Update, context: CallbackContext) -> None:
    """
    Handle incoming messages. Authenticate the user or provide recommendations based on the current state.
    """
    user_message = update.message.text
    logger.info(f"Received message: {user_message}")
    
    agent = AuthGraph(memory)
    thread = {"configurable": {"thread_id": update.message.from_user.id}}
    
    if 'poll_data' in agent.graph.get_state(thread).values:
        logger.info("User authenticated, providing recommendations")
        poll_data = agent.graph.get_state(thread).values['poll_data']
        response = get_answer_for_recommendation_graph(user_message, update.message.from_user.id, poll_data)
    else:
        logger.info("User not authenticated, proceeding with authentication")
        response = get_answer_for_auth_graph(agent, thread, user_message)
    
    await update.message.reply_text(response)

def main() -> None:
    """
    Main function to set up the Telegram bot and handlers.
    """
    logger.info("Starting bot")
    
    # Set up the application with the bot token
    application = ApplicationBuilder().token(tg_token).build()

    # Register the command and message handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot with polling
    application.run_polling()

# Apply nest_asyncio to handle async tasks
nest_asyncio.apply()

# Run the main function
if __name__ == "__main__":
    main()
