# graph.py
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from state import ContactState
from nodes import (
    askName, validateName,
    askEmail, validateEmail,
    askPhone, validatePhone,
    askMessage, completeForm, validateMessage,
    shouldContinueName, shouldContinueEmail, shouldContinuePhone,shouldContinueMessage
)

workflow = StateGraph(ContactState)

# ── Add all nodes ──
workflow.add_node("askName", askName)
workflow.add_node("validateName", validateName)
workflow.add_node("askEmail", askEmail)
workflow.add_node("validateEmail", validateEmail)
workflow.add_node("askPhone", askPhone)
workflow.add_node("validatePhone", validatePhone)
workflow.add_node("askMessage", askMessage)
workflow.add_node("validateMessage", validateMessage)   # ← new
workflow.add_node("completeForm", completeForm)

# ── Entry point ──
workflow.set_entry_point("askName")

# ── Straight edges ──
workflow.add_edge("askName", "validateName")
workflow.add_edge("askEmail", "validateEmail")
workflow.add_edge("askPhone", "validatePhone")
workflow.add_edge("askMessage", "validateMessage")      # ← was askMessage → saveToDB
workflow.add_edge("completeForm", END)

# ── Conditional edges ──
#
# ARCHITECTURE: On retry (is_valid=False), route back to the SAME validate node.
# The validate node already set bot_message to the specific error.
# The graph will hit interrupt_before that validate node and pause,
# sending the error message to the user — NOT a fresh ask-style greeting.
#
# On success (is_valid=True), advance to the next ask node.
#
# Conditional edges now route failures BACK to ask nodes, not validate nodes
workflow.add_conditional_edges(
    "validateName",
    shouldContinueName,
    {
        "askEmail": "askEmail",   # success
        "askName": "askName"      # failure — back to ask, which handles retry message
    }
)

workflow.add_conditional_edges(
    "validateEmail",
    shouldContinueEmail,
    {
        "askPhone": "askPhone",
        "askEmail": "askEmail"
    }
)

workflow.add_conditional_edges(
    "validatePhone",
    shouldContinuePhone,
    {
        "askMessage": "askMessage",
        "askPhone": "askPhone"
    }
)

# ── Conditional edge for message ──
workflow.add_conditional_edges(
    "validateMessage",
    shouldContinueMessage,
    {
       "completeForm": "completeForm",     # success
        "askMessage": "askMessage"  # failure
    }
)


# ── Checkpointer (SQLite) ──
conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
checkpointer = SqliteSaver(conn)

# ── Compile with interrupts ──
#
# interrupt_before these nodes so Flask can inject user input before they run:
#   - validateName/Email/Phone: user just typed their value → inject → validate
#   - saveToDB: user just typed their message → inject → save
#
# askName/Email/Phone/Message do NOT need interrupts — they generate bot prompts
# and flow straight through without needing user input first.
#

# graph.py — fix the interrupt_before list
app = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["validateName", "validateEmail", "validatePhone", "validateMessage"]
    #                  removed "saveToDB" ↑, added "validateMessage" ↑
)

if __name__ == "__main__":
    png_image = app.get_graph().draw_mermaid_png()
    with open("contact_form_graph.png", "wb") as f:
        f.write(png_image)
    print("Graph generated successfully!") 