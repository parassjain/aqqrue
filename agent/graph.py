"""
LangGraph StateGraph for the CSV agent.

Graph topology (ReAct pattern):
  START → agent_node → tools_condition → tool_node → agent_node → ... → END

The agent_node calls the LLM with bound tools.
The tool_node executes whatever tools the LLM requested.
tools_condition routes back to tool_node while tool_calls exist,
and to END when the LLM produces a plain text response.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent.tools import ALL_TOOLS
from config import get_llm


class AgentState(TypedDict):
    """Minimal graph state: just the message list.
    LangGraph's add_messages reducer appends new messages rather than replacing."""
    messages: Annotated[list[BaseMessage], add_messages]


def _build_agent_node(llm_with_tools):
    """Return a node function that calls the LLM and returns the response."""
    def agent_node(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
    return agent_node


def create_graph():
    """Compile and return the LangGraph graph.

    Call this once per user message (or cache it — the graph is stateless;
    all state lives in the messages passed to graph.stream()).
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    builder = StateGraph(AgentState)
    builder.add_node("agent", _build_agent_node(llm_with_tools))
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)   # → "tools" or END
    builder.add_edge("tools", "agent")

    return builder.compile()
