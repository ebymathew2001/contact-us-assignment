from llm import llm
from state import ContactState, BotResponse
from logger import logger


def completeForm(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    try:
        structured_llm = llm.with_structured_output(BotResponse)
        response = structured_llm.invoke(
            f"You are a friendly contact form assistant. "
            f"The user named {state.get('name', 'there')} has submitted their message: "
            f"'{state.get('message', '')}'. "
            f"Acknowledge their message warmly, thank them for filling out the form, "
            f"and tell them the team will get back to them soon. Keep it warm and concise (2-3 sentences). "
            f"Return field='done' and status='asking'."
        )

        final_data = {
            "name": state.get("name"),
            "email": state.get("email"),
            "phone": state.get("phone"),
            "message": state.get("message")
        }

        logger.info(f"session_id={session_id} form complete — Flask will save contact")

        return {
            **state,
            "final_data": final_data,
            "bot_message": response.message,
            "is_complete": True,
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=completeForm error={error_msg}")
        # CONTRACT: is_complete=True is the signal to app.py to write to contacts table.
# This is the ONLY place in the entire codebase that sets is_complete=True.
        return {
            **state,
            "bot_message": "Sorry, we had an issue finalising your details. Please try again.",
            "is_complete": False,
            "system_error": {
                "node": "completeForm",
                "error_type": "llm_error",
                "message": error_msg
            }
        }