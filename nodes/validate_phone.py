from llm import llm
from state import ContactState, ExtractedPhone
from tools import validate_name_tool, validate_email_tool, validate_phone_tool
from logger import logger


def validatePhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("phone", "").strip()

    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=phone input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": "You didn't type anything. Please enter your 10-digit phone number (digits only).",
            "bot_message": "",
            "system_error": {}
        }

    try:
        structured_llm = llm.with_structured_output(ExtractedPhone)
        extracted = structured_llm.invoke(
            f"Extract ONLY the local phone number digits from this input: '{raw_input}'. "
            f"Rules: remove all spaces, dashes, brackets, dots. "
            f"If a country code is present (like +91, +1, 0091, or a leading 0), remove it entirely. "
            f"Example: '+91 9876543210' → '9876543210', '987-654-3210' → '9876543210'. "
            f"Return digits only, no other characters."
        )
        clean_phone = extracted.phone.strip()
        logger.info(f"RAW PHONE: {raw_input} | CLEAN PHONE: {clean_phone}")

        if not clean_phone:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "validation_error": "I couldn't find a phone number in that. Please enter just the 10 digits of your phone number.",
                "bot_message": "",
                "system_error": {}
            }

        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this phone number: '{clean_phone}'. Use the validate_phone_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_phone_tool":
                validation_result = validate_phone_tool.invoke(tool_call["args"])
                break

        if validation_result is None:
            validation_result = validate_phone_tool.invoke({"phone": clean_phone})

        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=phone input={clean_phone} status=SUCCESS")
            return {
                **state,
                "phone": clean_phone,
                "is_valid": True,
                "retry_count": 0,
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        error_type = validation_result.get("error_type", "invalid_phone")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=phone input={clean_phone} error={error_type} retry={retry_count}")

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": tool_message,
            "bot_message": "",
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=validatePhone error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "validation_error": "Something went wrong while checking your phone number. Please try again.",
            "bot_message": "",
            "system_error": {
                "node": "validatePhone",
                "error_type": "tool_error",
                "message": error_msg
            }
        }