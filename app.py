from dotenv import load_dotenv

load_dotenv() 
from flask import Flask, request, jsonify, render_template
from graph import app as langgraph_app
from database import (
    create_tables, save_session, save_chat,
    save_error, save_contact,
    get_sessions, get_conversation, get_errors, get_details
)
from logger import logger

flask_app = Flask(__name__)


# Create all tables on startup
create_tables()


# ─────────────────────────────────────────────
# SERVE FRONTEND PAGES
# ─────────────────────────────────────────────
@flask_app.route("/")
def index():
    return render_template("index.html")


@flask_app.route("/logs-page")
def logs_page():
    return render_template("logs.html")


# ─────────────────────────────────────────────
# POST /chat/start
# Called by browser when chat widget opens
# ─────────────────────────────────────────────
@flask_app.route("/chat/start", methods=["POST"])
def chat_start():
    data = request.get_json()
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    # 1. Save session to DB immediately
    save_session(session_id)
    logger.info(f"session_id={session_id} new session created")

    # 2. Run graph from beginning — askName runs, pauses before validateName
    config = {"configurable": {"thread_id": session_id}}
    result = langgraph_app.invoke({
        "session_id": session_id,
        "name": "",
        "email": "",
        "phone": "",
        "message": "",
        "current_field": "name",
        "retry_count": 0,
        "is_valid": False,
        "final_data": {},
        "bot_message": "",
        "is_complete": False,
        "system_error": {}
    }, config=config)

    bot_reply = result.get("bot_message", "Hi! What is your name?")

    # 3. Save bot greeting to chats table
    save_chat(session_id, "bot", bot_reply)

    return jsonify({
        "response": bot_reply,
        "session_id": session_id
    })


# ─────────────────────────────────────────────
# POST /chat
# Called by browser on every user message
# Flask saves ALL DB records here after invoke()
# ─────────────────────────────────────────────
@flask_app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_message = data.get("message", "")

    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    config = {"configurable": {"thread_id": session_id}}

    # 1. Save user message to chats BEFORE invoking graph
    save_chat(session_id, "user", user_message)

    # 2. Get current state from checkpoint to know which field we are collecting
    current_state = langgraph_app.get_state(config)
    current_values = current_state.values if current_state else {}
    current_field = current_values.get("current_field", "name")

    # 3. ✅ CORRECT LANGGRAPH RESUME PATTERN
    #    Step 1 — update the state with user input in the right field
    #    Step 2 — resume graph from pause point by passing None
    #
    #    OLD (wrong): langgraph_app.invoke({current_field: user_message}, config=config)
    #    This could restart the graph from the beginning instead of resuming.
    #
    #    NEW (correct): update_state first, then invoke(None)
    #    invoke(None) means "resume from where you paused, don't restart"
    langgraph_app.update_state(config, {current_field: user_message})
    result = langgraph_app.invoke(None, config=config)

    bot_reply = result.get("bot_message", "")

    # 4. Save bot reply to chats
    save_chat(session_id, "bot", bot_reply)

    # 5. If a system crash happened inside a node, save it to errors table
    system_error = result.get("system_error", {})
    if system_error:
        save_error(
            session_id=session_id,
            node=system_error.get("node", "unknown"),
            error_type=system_error.get("error_type", "unknown"),
            message=system_error.get("message", "")
        )

    # 6. If form is complete, save contact data and update session status
    if result.get("is_complete"):
        save_contact(
            session_id=session_id,
            name=result.get("name", ""),
            email=result.get("email", ""),
            phone=result.get("phone", ""),
            message=result.get("message", "")
        )
        logger.info(f"session_id={session_id} contact saved successfully")

    return jsonify({
        "response": bot_reply,
        "session_id": session_id,
        "is_complete": result.get("is_complete", False)
    })
   


# ─────────────────────────────────────────────
# GET /logs?page=1&limit=10
# ─────────────────────────────────────────────
@flask_app.route("/logs", methods=["GET"])
def logs():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    result = get_sessions(page=page, limit=limit)
    return jsonify(result)


# ─────────────────────────────────────────────
# GET /logs/<session_id>/conversation
# ─────────────────────────────────────────────
@flask_app.route("/logs/<session_id>/conversation", methods=["GET"])
def logs_conversation(session_id):
    return jsonify(get_conversation(session_id))


# ─────────────────────────────────────────────
# GET /logs/<session_id>/errors
# ─────────────────────────────────────────────
@flask_app.route("/logs/<session_id>/errors", methods=["GET"])
def logs_errors(session_id):
    return jsonify(get_errors(session_id))


# ─────────────────────────────────────────────
# GET /logs/<session_id>/details
# ─────────────────────────────────────────────
@flask_app.route("/logs/<session_id>/details", methods=["GET"])
def logs_details(session_id):
    return jsonify(get_details(session_id))


if __name__ == "__main__":
    print("Server running on http://127.0.0.1:5000")
    flask_app.run(debug=True, port=5000, host="127.0.0.1", use_reloader=False)