
from dotenv import load_dotenv
_ = load_dotenv()

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, SystemMessage
from flight_info_tool import FlightInfoTool
from typing import Optional, Dict
from langchain.prompts import ChatPromptTemplate
from utils import get_pool_info_by_phone_number, schedule_daily_reminder, get_pool_data
from langchain_core.tools import ToolException
from datetime import datetime


class RecommendationState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    recommendation_message: str
    chat_id: int
    flight_info: Optional[Dict]
    assesment: Dict[str, str]
    after_tool_stop: bool
    flight_info_request: Dict
    


system_message_flight_template = ChatPromptTemplate.from_messages([
    ("system", """You are a flight search assistant. Given user's flight and flight date, call the tool for printing the info about this flight\\
Only look up information when you are sure of what you want, otherwise ask the user for information about flight.
If you get errors during running the search tool, just explain the error to the user and ask for information again.
Only call the tool once, when you are sure of the request.

Current chat id is: {chat_id}


Current date: {current_date}
""")
])


system_message_recommendation_template = ChatPromptTemplate.from_messages([
    ("system", """You are an expert in designing personalized, science-backed sleep and circadian protocols. 
     Your goal is to create a detailed, tailored plan that addresses an individual's chronotype and preferences, with the aim of enhancing their sleep quality and daytime alertness for dealing with jet lag. 
     Your recommendations should be actionable and time-specific."""),
    ("user", """Based on the provided circadian assessment (user's personal assessment), generate recommendations that are targeting melatonin, caffeine, physical activity, light exposure, sleep onset and offset timing.
     Here is the assesment data: {assesment}.
     
     Also, here are the base recommendations. You can use them as a starting point, modify them or add new ones:
    🌞 Take 0.5mg melatonin at 10:30pm to help advance your sleep onset
    ☕ Avoid caffeine after 3pm
    🌇 Get outdoor light exposure in the morning to help anchor your circadian clock
    🚶‍♂️ Do some light exercise like walking between 5-7pm
    (on your response, don't forget to include emojis and new lines for better readability. DON'T INCLUDE ANY COMMENTS OR EXPLANATIONS OR ADDITIONAL TEXT FORMATTING, OUTPUT ONLY THE LIST OF RECOMMENDATION)
    
    Here is the flight info: {flight_info}""")
])





class RecommendationGraph:

    def __init__(self, model, flight_info_prompt = system_message_flight_template, recommendation_prompt = system_message_recommendation_template):
        self.flight_info_prompt = flight_info_prompt
        self.recommendationPrompt = recommendation_prompt
        
        graph = StateGraph(RecommendationState)
        graph.add_node("llm", self.call_openai_flight_info_state)
        graph.add_node("action", self.take_action_state)
        graph.add_node("recommendation", self.call_openai_recommendation_state)
        graph.add_node("schedule", self.schedule_message_state)
        
        graph.add_conditional_edges(
            "llm",
            self.exists_action_transition,
            {True: "action", False: END}
        )
        graph.add_conditional_edges(
            "action",
            lambda state: state['after_tool_stop'],
            {True: END, False: "recommendation"}
        )
        graph.add_edge("recommendation", "schedule")
        graph.add_edge("schedule", END)
        
        graph.set_entry_point("llm")
        self.graph = graph.compile()
        self.flight_info_tool = FlightInfoTool()
        
        self.model = model
        self.model_with_tools = model.bind_tools([self.flight_info_tool])

    def exists_action_transition(self, state: RecommendationState):
        result = state['messages'][-1]
        return len(result.tool_calls) > 0

    def call_openai_flight_info_state(self, state: RecommendationState):
        messages = state['messages']
        messages = self.flight_info_prompt.invoke({"chat_id": state["chat_id"], "current_date": datetime.now()}).messages + messages
        result = self.model_with_tools.invoke(messages)
        return {'messages': [result]}
    
    
    def call_openai_recommendation_state(self, state: RecommendationState):
        messages = self.recommendationPrompt.invoke({"assesment": state["assesment"], "flight_info": state['flight_info']}).messages
        
        result = self.model.invoke(messages)
        return {"recommendation_message": result.content}
    
    
    def schedule_message_state(self, state: RecommendationState):
        recommendations_message= state['recommendation_message']
        # catch exception here 
        
        username = state['assesment']['What is your name?'] if state['assesment'] else "User"
        flight_data = state['flight_info']
        
        # convert datetime to str
        dep_date = flight_data['departure_date'].strftime("%B %d, %Y")
        origin = flight_data['departure_airport']
        destination = flight_data['arrival_airport']
        
        
        
        return_message = f"""Hi {username}, for your flight from {origin} to {destination} on {dep_date}, here is my recommendations for optimizing your sleep and alertness for today: \n\n{recommendations_message}\n\nThis gradual adjustment shifts the sleep-wake cycle ahead before your trip.
        """
        
        schedule_daily_reminder(recommendations_message, state['flight_info']['departure_date'], state['chat_id'])
        return {'messages': [SystemMessage(content=return_message)]}
    
    

    def take_action_state(self, state: RecommendationState):
        tool_calls = state['messages'][-1].tool_calls
        if len(tool_calls) > 1:
            raise ValueError("Only one tool call is supported")
        tool_call = tool_calls[0]
        if tool_call['name'] != "flight_info_tool":
            raise ValueError("Only flight_info_tool is supported")
        try:
            print(tool_call['args'])
            result = self.flight_info_tool.invoke(tool_call['args'])
            print("found the flight info")
            
            
        except ToolException as e:
            return {'messages': [SystemMessage(content=f"{e} Please try again.")], 'after_tool_stop': True}
        #result = ToolMessage(tool_call_id=tool_call['id'], name="flight_info_tool", content=str(result))
        #print("Back to the model!")
        return {'flight_info': result, 'after_tool_stop': False}