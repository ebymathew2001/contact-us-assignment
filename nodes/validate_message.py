from llm import llm
from state import ContactState, ExtractedDescription
from logger import logger

SKIP_PHRASES = {"skip", "no", "none", "na", "n/a", "nope", "no message", "nothing"}


def validateMessage(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("message", "").strip()

    # ── Empty or known skip phrase — accept immediately ──
    if not raw_input or raw_input.lower() in SKIP_PHRASES:
        logger.info(f"session_id={session_id} field=message status=SKIPPED")
        return {
            **state,
            "message": "",
            "is_valid": True,
            "retry_count": 0,
            "validation_error": "",
            "bot_message": "",
            "system_error": {}
        }

    # ── Use LLM to detect skip intent and extract clean message ──
    try:
        structured_llm = llm.with_structured_output(ExtractedDescription)
        extracted = structured_llm.invoke(
            f"The user was asked for an optional message or query. Their input: '{raw_input}'. "
            f"If they are trying to skip (saying skip, no, nothing, na etc.) set skipped=True and description=''. "
            f"Otherwise extract their actual message and set skipped=False."
        )

        # ── Skip intent detected by LLM ──
        if extracted.skipped:
            logger.info(f"session_id={session_id} field=message status=SKIPPED via LLM")
            return {
                **state,
                "message": "",
                "is_valid": True,
                "retry_count": 0,
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        clean_message = extracted.description.strip()

        # ── Too long ──
        if len(clean_message) > 1000:
            retry_count = state.get("retry_count", 0) + 1
            logger.warning(f"session_id={session_id} field=message input=TOO_LONG retry={retry_count}")
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "validation_error": f"Your message is too long ({len(clean_message)} characters). Please keep it under 1000 characters.",
                "bot_message": "",
                "system_error": {}
            }

        # ── Success ──
        logger.info(f"session_id={session_id} field=message status=SUCCESS length={len(clean_message)}")
        return {
            **state,
            "message": clean_message,
            "is_valid": True,
            "retry_count": 0,
            "validation_error": "",
            "bot_message": "",
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=validateMessage error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "validation_error": "Something went wrong. Please try again or type 'skip'.",
            "bot_message": "",
            "system_error": {
                "node": "validateMessage",
                "error_type": "llm_error",
                "message": error_msg
            }
        }