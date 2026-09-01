from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import RecoveryState

# Singleton checkpointer to preserve multi-turn state across the app's lifetime
_memory_saver = MemorySaver()

def dummy_node(state: RecoveryState) -> RecoveryState:
    """A dummy node for Phase 1 to ensure the graph compiles."""
    return {"next_agent": END}

def build_graph():
    """
    Builds and compiles the LangGraph StateGraph for the AI Revenue Recovery POC.
    Phase 1: Contains only a dummy node until agents are implemented.
    """
    workflow = StateGraph(RecoveryState)

    # Add dummy node
    workflow.add_node("intake", dummy_node)

    # Entry point
    workflow.add_edge(START, "intake")
    
    # Exit point
    workflow.add_edge("intake", END)

    return workflow.compile(checkpointer=_memory_saver)
