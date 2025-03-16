from langchain_core.messages import SystemMessage  
from langchain_openai import ChatOpenAI

from langgraph.graph import START, StateGraph, MessagesState
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver

from dotenv import load_dotenv
import os


load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

memory = MemorySaver()
react_graph_mem

def add(a: int | float, b: int | float) -> float:
    """Adds a and b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a + b

def multiply(a: int | float, b: int | float) -> float:
    """Multiplies a and b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a * b

def divide(a: int | float, b: int | float) -> float:
    """Divide a and b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a / b

def subtract(a: int | float, b: int | float) -> float:
    """Subtract a from b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a - b 

def power(a: int | float, b: int | float) -> float:
    """Raise a to the power of b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a ** b

def modulo(a: int | float, b: int | float) -> float:
    """Returns the remainder of a divided by b.

    Args:
        a: first number (int or float)
        b: second number (int or float)
    """
    return a % b

def absolute(a: int | float) -> float:
    """Returns the absolute value of a.

    Args:
        a: number (int or float)
    """
    return abs(a)

tools = [add, multiply, divide, subtract, power, modulo]

llm = ChatOpenAI(api_key=openai_api_key, model="gpt-3.5-turbo")
llm_with_tools = llm.bind_tools(tools)

sys_mes = SystemMessage(content="You are a calculator bot that can add, subtract, multiply, and divide numbers, but you have emmense knowledge of mathmatics and can uses these simple operations to solve complex problems. You can also chat with people and help them with their math")

def assistant(state: MessagesState):
    return {"messages": [llm_with_tools.invoke([sys_mes] + state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "assistant")
builder.add_edge("assistant", tools_condition)
builder.add_edge("tools", "assistant")

