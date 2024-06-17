import os
import logging
from typing import Any, Dict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai.chat_models.base import ChatOpenAI

from recommendation_graph import RecommendationGraph

# Load environment variables from a .env file
load_dotenv()

# Environment variables
LANGUAGE_MODEL = os.getenv("LANGUAGE_MODEL", "gpt-3.5-turbo")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def get_answer_for_auth_graph(agent: Any, thread_config: Dict[str, Any], user_message: str) -> str:
    """
    Get an answer from the authentication graph based on user message.
    """
    logger.info("Getting answer for authentication graph")
    current_values = agent.graph.get_state(thread_config)
    user_message = HumanMessage(content=user_message)
    current_values.values['last_message'] = user_message
    agent.graph.update_state(thread_config, current_values.values)

    for event in agent.graph.stream(None, thread_config):
        pass

    return agent.graph.get_state(thread_config).values['last_message'].content

def reset_auth_graph(agent: Any, thread_config: Dict[str, Any]) -> str:
    """
    Reset the authentication graph to its initial state.
    """
    logger.info("Resetting authentication graph")
    message = SystemMessage(content="Start")
    for event in agent.graph.stream({"last_message": message, 'poll_data': None}, thread_config):
        pass

    return agent.graph.get_state(thread_config).values['last_message'].content

def get_answer_for_recommendation_graph(user_message: str, chat_id: str, poll_data: Dict[str, Any]) -> str:
    """
    Get an answer from the recommendation graph based on user message and poll data.
    """
    logger.info("Getting answer for recommendation graph")
    llm = ChatOpenAI(model=LANGUAGE_MODEL)
    recommendation_graph = RecommendationGraph(llm)
    messages = [HumanMessage(content=user_message)]
    result = recommendation_graph.graph.invoke({"messages": messages, "chat_id": chat_id, "assessment": poll_data})
    return result['messages'][-1].content