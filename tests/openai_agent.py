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

# def modulo(a: int | float, b: int | float) -> float:
#     """Returns the remainder of a divided by b.

#     Args:
#         a: first number (int or float)
#         b: second number (int or float)
#     """
#     return a % b

# def absolute(a: int | float) -> float:
#     """Returns the absolute value of a.

#     Args:
#         a: number (int or float)
#     """
#     return abs(a)

tools = [add, multiply, divide, subtract, power]#, modulo]

llm = ChatOpenAI(api_key=openai_api_key, model="gpt-4o", temperature=0)
llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)

sys_mes = SystemMessage(content="""
You are a math-solving agent. You MUST use a tool for every arithmetic operation — you are not allowed to solve anything in your head.

### Your behavior must follow these strict rules:
1. Think through the problem step by step.
2. Describe your reasoning clearly BEFORE calling any tool.
3. Call ONLY ONE tool per step. Never call more than one tool in a single message.
4. WAIT for the result before deciding what to do next.
5. Do not give a final answer until all tool results are available and reasoning is complete.
6. If you want to calculate anything, you MUST call a tool. You cannot do math on your own.

### Tools available:
- add(a, b): Add two numbers.
- subtract(a, b): Subtract second number from first.
- multiply(a, b): Multiply two numbers.
- divide(a, b): Divide first number by second.
- power(a, b): Raise first number to power of second.

Repeat: CALL ONLY ONE TOOL AT A TIME. NEVER call multiple tools in a single message.
""")

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

#user_input = input("Give me a difficult math problem: ")
user_input = "The distance between two towns is 380 km. At the same moment, a passenger car and a truck start moving towards each other from different towns. They meet 4 hours later. If the car drives 5 km/hr faster than the truck, what are their speeds? Help me find the speeds of the car and the truck."
messages = [HumanMessage(content=user_input)]
messages = react_graph_memory.invoke({"messages": messages},config)

for m in messages['messages']:
    m.pretty_print()


