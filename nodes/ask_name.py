from llm import llm
from state import ContactState, BotResponse
from logger import logger


def askName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    retry_count = state.get("retry_count", 0)
    validation_error = state.get("validation_error", "")

    if retry_count > 0 and validation_error:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                f"You are a friendly contact form assistant. "
                f"The user tried to enter their name but it was invalid. "
                f"The specific reason: {validation_error} "
                f"Write a SHORT warm reply (1-2 sentences) that explains the problem "
                f"and asks them to try again. Do NOT say Hi or Hello. "
                f"Return field='name' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askName LLM error: {e}")
            message = f"That name didn't work — {validation_error} Please try again."
    else:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                "You are a friendly contact form assistant. "
                "Greet the user warmly and ask for their full name. "
                "Keep it short and friendly. Return field='name' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askName LLM error: {e}")
            message = "Hi there! Could you please share your full name to get started?"

    logger.info(f"session_id={session_id} askName retry={retry_count}")
    return {
        **state,
        "current_field": "name",
        "bot_message": message,
        "validation_error": "",
        "system_error": {}
    }