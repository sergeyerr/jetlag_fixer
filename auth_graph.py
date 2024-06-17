import logging
import re
from typing import TypedDict, Dict, Any

from langgraph.graph import StateGraph, END
from langchain_core.messages import AnyMessage, SystemMessage
from poll_utils import get_poll_info_by_phone_number, check_if_phone_number_exists

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AuthState(TypedDict):
    last_message: AnyMessage
    poll_data: Dict[str, str]

class AuthGraph:
    def __init__(self, checkpointer: Any, system: str = "") -> None:
        self.system = system
        graph = StateGraph(AuthState)
        graph.add_node("start", self.start)
        graph.add_node("invalid_phone_format", self.invalid_phone_format)
        graph.add_node("no_poll_data", self.no_poll_data)
        graph.add_node("message_interrupt", self.message_interrupt)
        graph.add_node("write_poll_data", self.write_poll_data)
        
        graph.add_conditional_edges(
            "message_interrupt",
            self.check_phone_format_transition
        )
        
        graph.add_edge("start", "message_interrupt")
        graph.add_edge("invalid_phone_format", "message_interrupt")
        graph.add_edge("no_poll_data", "message_interrupt")
        graph.add_edge("write_poll_data", END)
        
        graph.set_entry_point("start")
        self.graph = graph.compile(
            interrupt_before=["message_interrupt"],
            checkpointer=checkpointer,
        )
        
    def check_phone_format_transition(self, state: AuthState) -> str:
        """
        Check if the phone number format is valid and if poll data exists.
        """
        phone_number = state['last_message'].content
        logger.info(f"Checking phone number format: {phone_number}")
        
        # The phone number should be in format +11234565789 (variable length)
        passes = re.match(r'^\+\d+$', phone_number)
        
        if not passes:
            logger.warning("Invalid phone number format")
            return "invalid_phone_format"
        
        phone_number = phone_number.replace("+", "")
        if not check_if_phone_number_exists(int(phone_number)):
            logger.warning("No poll data found for phone number")
            return "no_poll_data"

        logger.info("Poll data found for phone number")
        return "write_poll_data"
            
    def message_interrupt(self, state: AuthState) -> Dict[str, Any]:
        """
        Handle message interrupt state.
        """
        logger.info("Message interrupt state")
        return {'last_message': state['last_message']}
        
    def start(self, state: AuthState) -> Dict[str, Any]:
        """
        Initial state of the authentication graph.
        """
        logger.info("Starting authentication process")
        return {'last_message': SystemMessage(
            "Welcome to the Jetlag Fixer! 🌙 It seems you're not registered yet. "
            "Complete our circadian assessment to get recommendations that align with your internal clocks! \n"
            "Please enter your phone number to get started. Use the format with the country code and without spaces, e.g. +11234565789."
        )}
    
    def retype_phone(self, state: AuthState) -> Dict[str, Any]:
        """
        State to prompt user to retype phone number.
        """
        logger.info("Prompting user to retype phone number")
        return {'last_message': SystemMessage(
            "Please retype your phone number using the format with the country code and without spaces, e.g. +11234565789."
        )}
    
    def invalid_phone_format(self, state: AuthState) -> Dict[str, Any]:
        """
        State when the phone number format is invalid.
        """
        logger.info("Invalid phone format state")
        return {'last_message': SystemMessage(
            "The phone number you entered is invalid. Please enter a valid phone number."
        )}
    
    def no_poll_data(self, state: AuthState) -> Dict[str, Any]:
        """
        State when no poll data is found for the phone number.
        """
        logger.info("No poll data state")
        return {'last_message': SystemMessage(
            "We could not find any poll data for the phone number you entered. Please fill the form and enter a valid phone number again. \n\n https://form.typeform.com/to/Wv8KDBuG"
        )}
    
    def write_poll_data(self, state: AuthState) -> Dict[str, Any]:
        """
        State to write poll data after successful authentication.
        """
        logger.info("Writing poll data")
        phone_number = state['last_message'].content
        phone_number = phone_number.replace("+", "")
        poll_data = get_poll_info_by_phone_number(int(phone_number))
        
        return {
            'poll_data': poll_data,
            'last_message': SystemMessage(
                "You have been successfully authenticated! Now you can enter your flight number and date."
            )
        }
