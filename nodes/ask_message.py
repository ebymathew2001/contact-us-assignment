from llm import llm
from state import ContactState, BotResponse
from logger import logger


def askMessage(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    retry_count = state.get("retry_count", 0)
    validation_error = state.get("validation_error", "")

    if retry_count > 0 and validation_error:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                f"You are a friendly contact form assistant. "
                f"The user tried to submit their message but it was invalid. "
                f"The specific reason: {validation_error} "
                f"Write a SHORT warm reply (1-2 sentences) that explains the problem "
                f"and asks them to try again. Do NOT say Hi or Hello. "
                f"Return field='message' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askMessage LLM error: {e}")
            message = f"Your message didn't go through — {validation_error} Please try again."
    else:
        try:
            structured_llm = llm.with_structured_output(BotResponse)
            prompt = (
                "You are a friendly contact form assistant. All details collected. "
                "Now ask the user to type their message or query for the team. "
                "Keep it short and warm (1-2 sentences). Do NOT say Hi or Hello again. "
                "Return field='message' and status='asking'."
            )
            response = structured_llm.invoke(prompt)
            message = response.message
        except Exception as e:
            logger.error(f"session_id={session_id} askMessage LLM error: {e}")
            message = "Almost done! Please type your message or query for our team."

    logger.info(f"session_id={session_id} askMessage retry={retry_count}")
    return {
        **state,
        "current_field": "message",
        "bot_message": message,
        "validation_error": "",
        "system_error": {}
    }