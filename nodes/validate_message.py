from state import ContactState
from logger import logger


def validateMessage(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("message", "").strip()

    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=message input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": "You didn't type anything. Please enter your message.",
            "bot_message": "",
            "system_error": {}
        }

    if len(raw_input) < 10:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=message input=TOO_SHORT retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": f"Your message is too short ({len(raw_input)} characters). Please write at least 10 characters so we can understand your query.",
            "bot_message": "",
            "system_error": {}
        }

    if len(raw_input) > 1000:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=message input=TOO_LONG retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": f"Your message is too long ({len(raw_input)} characters). Please keep it under 1000 characters.",
            "bot_message": "",
            "system_error": {}
        }

    logger.info(f"session_id={session_id} field=message status=SUCCESS length={len(raw_input)}")
    return {
        **state,
        "message": raw_input,
        "is_valid": True,
        "retry_count": 0,
        "validation_error": "",
        "bot_message": "",
        "system_error": {}
    }