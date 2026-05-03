# graph.py
import sqlite3
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from state import ContactState
from nodes import (
    askName, validateName,
    askEmail, validateEmail,
    askPhone, validatePhone,
    askMessage, saveToDB,
    shouldContinueName, shouldContinueEmail, shouldContinuePhone
)

workflow = StateGraph(ContactState)

# Add all nodes
workflow.add_node("askName", askName)
workflow.add_node("validateName", validateName)
workflow.add_node("askEmail", askEmail)
workflow.add_node("validateEmail", validateEmail)
workflow.add_node("askPhone", askPhone)
workflow.add_node("validatePhone", validatePhone)
workflow.add_node("askMessage", askMessage)
workflow.add_node("saveToDB", saveToDB)

# Entry point
workflow.set_entry_point("askName")

# Straight edges
workflow.add_edge("askName", "validateName")
workflow.add_edge("askEmail", "validateEmail")
workflow.add_edge("askPhone", "validatePhone")
workflow.add_edge("askMessage", "saveToDB")
workflow.add_edge("saveToDB", END)

# Conditional edges
workflow.add_conditional_edges("validateName", shouldContinueName,
    {"askEmail": "askEmail", "askName": "askName"})

workflow.add_conditional_edges("validateEmail", shouldContinueEmail,
    {"askPhone": "askPhone", "askEmail": "askEmail"})

workflow.add_conditional_edges("validatePhone", shouldContinuePhone,
    {"askMessage": "askMessage", "askPhone": "askPhone"})

# ✅ correct way — pass sqlite3 connection directly
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["validateName", "validateEmail", "validatePhone", "saveToDB"]
)


if __name__ == "__main__":
    png_image = app.get_graph().draw_mermaid_png()
    with open("contact_form_graph.png", "wb") as f:
        f.write(png_image)
    print("Graph generated successfully!")