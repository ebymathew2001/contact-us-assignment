from llm import llm
from state import ContactState, ExtractedName
from tools import validate_name_tool, validate_email_tool, validate_phone_tool
from logger import logger


def validateName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("name", "").strip()

    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=name input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": "You didn't type anything. Please enter your full name.",
            "bot_message": "",
            "system_error": {}
        }

    try:
        structured_llm = llm.with_structured_output(ExtractedName)
        extracted = structured_llm.invoke(
            f"Extract ONLY the person's actual name from this input: '{raw_input}'. "
            f"Rules: "
            f"1) Remove filler phrases like 'my name is', 'I am', 'call me', 'it is', etc. "
            f"2) Return ONLY the name words themselves, nothing else. "
            f"3) If the input is a number, symbol, or unrelated sentence, return it as-is. "
            f"4) Do NOT interpret or invent — return exactly what remains after removing filler. "
            f"Examples: "
            f"'my name is eby mathew' → 'eby mathew' "
            f"'I am john' → 'john' "
            f"'my name is full name' → 'full name' "
            f"'123' → '123' "
            f"'what is the weather' → 'what is the weather' "
        )
        clean_name = extracted.name.strip() if extracted.name else raw_input.strip()
        logger.info(f"RAW NAME: {raw_input} | CLEAN NAME: {clean_name}")

        if not clean_name:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "validation_error": "I couldn't find a name in that input. Please type just your full name.",
                "bot_message": "",
                "system_error": {}
            }

        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this name: '{clean_name}'. Use the validate_name_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_name_tool":
                validation_result = validate_name_tool.invoke(tool_call["args"])
                break

        if validation_result is None:
            validation_result = validate_name_tool.invoke({"name": clean_name})

        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=name input={clean_name} status=SUCCESS")
            return {
                **state,
                "name": clean_name,
                "is_valid": True,
                "retry_count": 0,
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        error_type = validation_result.get("error_type", "unknown_error")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=name input={clean_name} error={error_type} retry={retry_count}")

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
        logger.error(f"session_id={session_id} node=validateName error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "validation_error": "Something went wrong while checking your name. Please try again.",
            "bot_message": "",
            "system_error": {
                "node": "validateName",
                "error_type": "tool_error",
                "message": error_msg
            }
        }