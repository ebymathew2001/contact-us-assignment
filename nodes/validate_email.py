from llm import llm
from state import ContactState, ExtractedEmail
from tools import validate_name_tool, validate_email_tool, validate_phone_tool
from logger import logger


def validateEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("email", "").strip()

    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=email input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": "You didn't type anything. Please enter your email address (e.g. name@example.com).",
            "bot_message": "",
            "system_error": {}
        }

    try:
        structured_llm = llm.with_structured_output(ExtractedEmail)
        extracted = structured_llm.invoke(
            f"Extract ONLY the email address from this input: '{raw_input}'. "
            f"Remove any extra words like 'my email is', 'it is', 'email:', etc. "
            f"Return just the email address itself."
        )
        clean_email = extracted.email.strip()
        logger.info(f"RAW EMAIL: {raw_input} | CLEAN EMAIL: {clean_email}")

        if not clean_email:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "validation_error": "I couldn't find an email address in that. Please type just your email (e.g. name@example.com).",
                "bot_message": "",
                "system_error": {}
            }

        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this email address: '{clean_email}'. Use the validate_email_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_email_tool":
                validation_result = validate_email_tool.invoke(tool_call["args"])
                break

        if validation_result is None:
            validation_result = validate_email_tool.invoke({"email": clean_email})

        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=email input={clean_email} status=SUCCESS")
            return {
                **state,
                "email": clean_email,
                "is_valid": True,
                "retry_count": 0,
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        error_type = validation_result.get("error_type", "invalid_format")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=email input={clean_email} error={error_type} retry={retry_count}")

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
        logger.error(f"session_id={session_id} node=validateEmail error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "validation_error": "Something went wrong while checking your email. Please try again.",
            "bot_message": "",
            "system_error": {
                "node": "validateEmail",
                "error_type": "tool_error",
                "message": error_msg
            }
        }