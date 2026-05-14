from llm import llm
from state import ContactState, BotResponse
from logger import logger


def askEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    retry_count = state.get("retry_count", 0)
    validation_error = state.get("validation_error", "")

    if retry_count > 0 and validation_error:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                f"You are a friendly contact form assistant. "
                f"The user tried to enter their email but it was invalid. "
                f"The specific reason: {validation_error} "
                f"Write a SHORT warm reply (1-2 sentences) that explains the problem, "
                f"shows an example like name@example.com, and asks them to try again. "
                f"Do NOT say Hi or Hello. "
                f"Return field='email' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askEmail LLM error: {e}")
            message = f"That email didn't work — {validation_error} Please try again (e.g. name@example.com)."
    else:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                f"You are a friendly contact form assistant. "
                f"The user's name is {state.get('name', 'there')}. "
                f"Ask for their email address in a friendly way. "
                f"Keep it short (1 sentence). Do NOT say Hi or Hello. "
                f"Return field='email' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askEmail LLM error: {e}")
            message = f"Thanks {state.get('name', 'there')}! Could you share your email address?"

    logger.info(f"session_id={session_id} askEmail retry={retry_count}")
    return {
        **state,
        "current_field": "email",
        "bot_message": message,
        "validation_error": "",
        "system_error": {}
    }