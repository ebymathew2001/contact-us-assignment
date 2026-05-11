from llm import llm
from state import ContactState, BotResponse
from logger import logger


def askPhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    retry_count = state.get("retry_count", 0)
    validation_error = state.get("validation_error", "")

    if retry_count > 0 and validation_error:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                f"You are a friendly contact form assistant. "
                f"The user tried to enter their phone number but it was invalid. "
                f"The specific reason: {validation_error} "
                f"Write a SHORT warm reply (1-2 sentences) that explains the problem, "
                f"reminds them it must be exactly 10 digits, and asks them to try again. "
                f"Do NOT say Hi or Hello. "
                f"Return field='phone' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askPhone LLM error: {e}")
            message = f"That phone number didn't work — {validation_error} Please enter exactly 10 digits."
    else:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                "You are a friendly contact form assistant. "
                "Ask the user for their 10-digit phone number. "
                "Keep it short (1 sentence). Do NOT say Hi or Hello. "
                "Return field='phone' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askPhone LLM error: {e}")
            message = "Could you please share your 10-digit phone number? (digits only)"

    logger.info(f"session_id={session_id} askPhone retry={retry_count}")
    return {
        **state,
        "current_field": "phone",
        "bot_message": message,
        "validation_error": "",
        "system_error": {}
    }