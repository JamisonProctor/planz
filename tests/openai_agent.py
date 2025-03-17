from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from langgraph.graph import START, StateGraph, MessagesState
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver

from dotenv import load_dotenv
import os


load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

memory = MemorySaver()


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
    """Divide a by b.

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

llm = ChatOpenAI(api_key=openai_api_key, model="gpt-3.5-turbo", temperature=0)
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)

sys_mes = SystemMessage(content='''
You are a step-by-step calculator agent. Your job is to solve math problems by thinking out loud 
and using tools to perform every arithmetic operation — even simple ones. Do not solve anything in your head. 
Always call the appropriate tool.

Rules:
- Think through the problem step by step.
- Use one tool at a time.
- Describe your reasoning before calling a tool.
- Only provide final answers after tool results are available.
''')

def assistant(state: MessagesState):
    return {"messages": [llm_with_tools.invoke([sys_mes] + state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")

react_graph = builder.compile()
react_graph_memory = builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "1"}}

user_input = input("Give me a difficult math problem: ")
messages = [HumanMessage(content=user_input)]
messages = react_graph_memory.invoke({"messages": messages},config)

for m in messages['messages']:
    m.pretty_print()


