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

    save_session(session_id)
    logger.info(f"session_id={session_id} new session created")

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
        "validation_error": "",   # ← ONLY CHANGE NEEDED
        "final_data": {},
        "bot_message": "",
        "is_complete": False,
        "system_error": {}
    }, config=config)

    bot_reply = result.get("bot_message", "Hi! What is your name?")
    save_chat(session_id, "bot", bot_reply)

    return jsonify({
        "response": bot_reply,
        "session_id": session_id
    })


# ─────────────────────────────────────────────
# POST /chat
# Called by browser on every user message
# ─────────────────────────────────────────────
@flask_app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    session_id = data.get("session_id")
    user_message = data.get("message", "").strip()

    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    config = {"configurable": {"thread_id": session_id}}

    # 1. Save user message to chats
    save_chat(session_id, "user", user_message)

    # 2. Get current state to know which field we are collecting
    current_state = langgraph_app.get_state(config)
    current_values = current_state.values if current_state else {}
    current_field = current_values.get("current_field", "name")

    logger.info(f"session_id={session_id} current_field={current_field} user_input='{user_message}'")

    # 3. Update state with user input in the correct field, then resume
    #
    # IMPORTANT: On retry, current_field is still the same (e.g. "email") because
    # the validate node sets it and the ask node never ran again.
    # So update_state({current_field: user_message}) correctly overwrites
    # the previous bad input with the new attempt.
    #
    # We also reset is_valid to False before resuming so the validate node
    # starts fresh (defensive — validate always sets it explicitly anyway).
    #
    langgraph_app.update_state(config, {
        current_field: user_message,
        "is_valid": False  # defensive reset before validation runs
    })
    result = langgraph_app.invoke(None, config=config)

    bot_reply = result.get("bot_message", "")

    # 4. Save bot reply
    save_chat(session_id, "bot", bot_reply)

    # 5. Save system errors if any
    system_error = result.get("system_error", {})
    if system_error:
        save_error(
            session_id=session_id,
            node=system_error.get("node", "unknown"),
            error_type=system_error.get("error_type", "unknown"),
            message=system_error.get("message", "")
        )

    # 6. If form complete, save contact data
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


@flask_app.route("/logs/<session_id>/conversation", methods=["GET"])
def logs_conversation(session_id):
    return jsonify(get_conversation(session_id))


@flask_app.route("/logs/<session_id>/errors", methods=["GET"])
def logs_errors(session_id):
    return jsonify(get_errors(session_id))


@flask_app.route("/logs/<session_id>/details", methods=["GET"])
def logs_details(session_id):
    return jsonify(get_details(session_id))


if __name__ == "__main__":
    print("Server running on http://127.0.0.1:5000")
    flask_app.run(debug=True, port=5000, host="127.0.0.1", use_reloader=False)