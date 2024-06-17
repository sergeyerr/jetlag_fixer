from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, Dict
from langchain_core.messages import AnyMessage, SystemMessage
from utils import  get_pool_info_by_phone_number, check_if_phone_number_exists
import regex as re

class AuthState(TypedDict):
    last_message: AnyMessage
    pool_data: Dict[str, str]

class AuthGraph:

    def __init__(self, checkpointer, system=""):
        self.system = system
        graph = StateGraph(AuthState)
        graph.add_node("start", self.start)
        graph.add_node("invalide_phone_format", self.invalid_phone_format)
        graph.add_node("no_pool_data", self.no_pool_data)
        graph.add_node("message_interrupt", self.message_interrupt)
        graph.add_node("write_pool_data", self.write_pool_data)
        
        
        graph.add_conditional_edges(
            "message_interrupt",
            self.check_phone_format_transition
        )
        
        graph.add_edge("start", "message_interrupt")
        graph.add_edge("invalide_phone_format", "message_interrupt")
        graph.add_edge("no_pool_data", "message_interrupt")
        graph.add_edge("write_pool_data", END)
        
        graph.set_entry_point("start")
        self.graph = graph.compile(
            # states where user input is expected
            interrupt_before=["message_interrupt"],
            checkpointer=checkpointer,
        )
        
        
    
    def check_phone_format_transition(self, state: AuthState):
        phone_number = state['last_message'].content
        # the phone should be in format +11234565789 (variable length)
        # write the regex to check this
        passes = re.match(r'^\+\d+$', phone_number)
        
        if not passes:
            return "invalide_phone_format"
        
        else:
            phone_number = phone_number.replace("+", "")
            pool_data = check_if_phone_number_exists(int(phone_number))
            
            if not pool_data:
                return "no_pool_data"

            else:
                return "write_pool_data"
            
    def message_interrupt(self, state: AuthState):

        # just copy the last message
        return {'last_message': state['last_message']}
        
    def start(self, state: AuthState):
        return {'last_message': SystemMessage("Welcome to the Jetlag Fixer! 🌙 It seems you're not registered yet. Complete our circadian assessment to get recommendations that align with your internal clocks! \n Please enter your phone number to get started. Use the format with the country code and without spaces, e.g. +11234565789.")}
    
    def retype_phone(self, state: AuthState):
        return {'last_message': SystemMessage("Please retype your phone number using the format with the country code and without spaces, e.g. +11234565789.")}
    
    def invalid_phone_format(self, state: AuthState):
        return {'last_message': SystemMessage("The phone number you entered is invalid. Please enter a valid phone number.")}
    
    def no_pool_data(self, state: AuthState):
        return {'last_message': SystemMessage("We could not find any pool data for the phone number you entered. Please fill the form and enter a valid phone number again. \n\n https://form.typeform.com/to/Wv8KDBuG")}
    
    def write_pool_data(self, state: AuthState):
        phone_number = state['last_message'].content
        phone_number = phone_number.replace("+", "")
        pool_data = get_pool_info_by_phone_number(int(phone_number))
        
        return {'pool_data': pool_data, 'last_message': SystemMessage("You have been successfully authenticated! Now you can enter you flight number and date")}
    

        
