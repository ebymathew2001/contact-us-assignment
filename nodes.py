# nodes.py
from langchain_groq import ChatGroq
from state import ContactState, BotResponse, ErrorResponse, ExtractedName, ExtractedEmail, ExtractedPhone
from tools import validate_name_tool, validate_email_tool, validate_phone_tool
from logger import logger
import os

# Initialize LLM — Groq API
llm = ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.environ.get("GROQ_API_KEY")
)


# ─────────────────────────────────────────────
# NODE 1 — askName
# ONLY runs at conversation start (entry point).
# On retry, validateName handles the re-ask message directly.
# ─────────────────────────────────────────────
def askName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    logger.info(f"session_id={session_id} conversation started")

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        "You are a friendly contact form assistant. Greet the user warmly and ask for their full name. "
        "Keep it short and friendly. Return field='name' and status='asking'."
    )

    return {
        **state,
        "current_field": "name",
        "bot_message": response.message,
        "system_error": {}
    }


# ─────────────────────────────────────────────
# NODE 2 — validateName
# Validates user input. On failure, sets bot_message to the error
# and routes back to itself (not askName) so the error is shown directly.
# ─────────────────────────────────────────────
def validateName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("name", "").strip()

    # ── Edge case: user submitted empty/whitespace ──
    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=name input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": "It looks like you didn't type anything! Could you please enter your full name?",
            "system_error": {}
        }

    try:
        # STEP 1 — Extract clean name (remove "my name is", "I am", etc.)
        structured_llm = llm.with_structured_output(ExtractedName)
        extracted = structured_llm.invoke(
            f"Extract ONLY the person's actual name from this input: '{raw_input}'. "
            f"Remove phrases like 'my name is', 'I am', 'call me', etc. "
            f"If the input contains no recognisable name (e.g. it is a number, symbol, or unrelated question), "
            f"return the input as-is so it can be validated and rejected. "
            f"Return just the name itself, nothing else."
        )
        clean_name = extracted.name.strip() if extracted.name else raw_input.strip()
        logger.info(f"RAW NAME: {raw_input} | CLEAN NAME: {clean_name}")

        # Guard: if extraction returned empty
        if not clean_name:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "bot_message": "I couldn't catch your name from that. Could you type just your full name?",
                "system_error": {}
            }

        # STEP 2 — Validate using tool
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this name: '{clean_name}'. Use the validate_name_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_name_tool":
                validation_result = validate_name_tool.invoke(tool_call["args"])
                break

        # Guard: tool never called (LLM didn't call the tool)
        if validation_result is None:
            # Fall back to direct tool call
            validation_result = validate_name_tool.invoke({"name": clean_name})

        # STEP 3 — Success
        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=name input={clean_name} status=SUCCESS")
            return {
                **state,
                "name": clean_name,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }

        # STEP 4 — Validation failed — generate specific error message
        error_type = validation_result.get("error_type", "unknown_error")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=name input={clean_name} error={error_type} retry={retry_count}")

        structured_llm = llm.with_structured_output(ErrorResponse)
        error_response = structured_llm.invoke(
            f"You are a friendly contact form assistant. The user was asked for their full name. "
            f"They entered: '{clean_name}'. "
            f"This failed validation. The specific reason is: {tool_message} "
            f"Write a SHORT, warm reply (1-2 sentences) that: "
            f"1) acknowledges what they typed, "
            f"2) explains the exact problem in plain language, "
            f"3) asks them to try again. "
            f"Do NOT say 'Hi' or 'Hello'. Do NOT greet them again. "
            f"Do NOT sound like you are asking for their name for the first time. "
            f"This is retry attempt {retry_count}. "
            f"Return field='name', error_type='{error_type}', retry_count={retry_count}."
        )

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": error_response.message,
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=validateName error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "bot_message": "Sorry, something went wrong. Please try entering your name again.",
            "system_error": {
                "node": "validateName",
                "error_type": "tool_error",
                "message": error_msg
            }
        }


# ─────────────────────────────────────────────
# NODE 3 — askEmail
# ONLY runs after name is successfully validated.
# On retry, validateEmail handles the re-ask message directly.
# ─────────────────────────────────────────────
def askEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        f"You are a friendly contact form assistant. The user's name is {state.get('name', 'there')}. "
        f"Ask for their email address in a friendly way. Keep it short (1 sentence). "
        f"Do NOT say Hi or Hello — just ask for the email. "
        f"Return field='email' and status='asking'."
    )

    return {
        **state,
        "current_field": "email",
        "bot_message": response.message,
        "system_error": {}
    }


# ─────────────────────────────────────────────
# NODE 4 — validateEmail
# On failure, sets bot_message to specific error and routes back to itself.
# ─────────────────────────────────────────────
def validateEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("email", "").strip()

    # ── Edge case: user submitted empty/whitespace ──
    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=email input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": "It looks like you didn't type anything! Please enter your email address (e.g. name@example.com).",
            "system_error": {}
        }

    try:
        # STEP 1 — Extract clean email
        structured_llm = llm.with_structured_output(ExtractedEmail)
        extracted = structured_llm.invoke(
            f"Extract ONLY the email address from this input: '{raw_input}'. "
            f"Remove any extra words like 'my email is', 'it is', 'email:', etc. "
            f"Return just the email address itself."
        )
        clean_email = extracted.email.strip()
        logger.info(f"RAW EMAIL: {raw_input} | CLEAN EMAIL: {clean_email}")

        # Guard: extraction returned empty
        if not clean_email:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "bot_message": "I couldn't find an email address in that. Could you type just your email? (e.g. name@example.com)",
                "system_error": {}
            }

        # STEP 2 — Validate using tool
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this email address: '{clean_email}'. Use the validate_email_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_email_tool":
                validation_result = validate_email_tool.invoke(tool_call["args"])
                break

        # Guard: tool never called
        if validation_result is None:
            validation_result = validate_email_tool.invoke({"email": clean_email})

        # STEP 3 — Success
        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=email input={clean_email} status=SUCCESS")
            return {
                **state,
                "email": clean_email,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }

        # STEP 4 — Validation failed
        error_type = validation_result.get("error_type", "invalid_format")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=email input={clean_email} error={error_type} retry={retry_count}")

        structured_llm = llm.with_structured_output(ErrorResponse)
        error_response = structured_llm.invoke(
            f"You are a friendly contact form assistant. The user was asked for their email address. "
            f"They entered: '{clean_email}'. "
            f"This failed validation. The specific reason is: {tool_message} "
            f"Write a SHORT, warm reply (1-2 sentences) that: "
            f"1) acknowledges what they typed, "
            f"2) explains the exact problem clearly (e.g. missing @, incomplete domain), "
            f"3) shows a quick example like name@example.com, "
            f"4) asks them to try again. "
            f"Do NOT say 'Hi' or 'Hello'. Do NOT greet them again. "
            f"Do NOT sound like this is the first time asking. "
            f"This is retry attempt {retry_count}. "
            f"Return field='email', error_type='{error_type}', retry_count={retry_count}."
        )

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": error_response.message,
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=validateEmail error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "bot_message": "Sorry, something went wrong. Please try entering your email again.",
            "system_error": {
                "node": "validateEmail",
                "error_type": "tool_error",
                "message": error_msg
            }
        }


# ─────────────────────────────────────────────
# NODE 5 — askPhone
# ONLY runs after email is successfully validated.
# ─────────────────────────────────────────────
def askPhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        "You are a friendly contact form assistant. Ask the user for their 10-digit phone number. "
        "Keep it short (1 sentence). Do NOT say Hi or Hello. "
        "Return field='phone' and status='asking'."
    )

    return {
        **state,
        "current_field": "phone",
        "bot_message": response.message,
        "system_error": {}
    }


# ─────────────────────────────────────────────
# NODE 6 — validatePhone
# On failure, sets bot_message to specific error and routes back to itself.
# ─────────────────────────────────────────────
def validatePhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("phone", "").strip()

    # ── Edge case: user submitted empty/whitespace ──
    if not raw_input:
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=phone input=EMPTY retry={retry_count}")
        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": "It looks like you didn't type anything! Please enter your 10-digit phone number (digits only).",
            "system_error": {}
        }

    try:
        # STEP 1 — Extract clean phone digits
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

        # Guard: extraction returned empty
        if not clean_phone:
            retry_count = state.get("retry_count", 0) + 1
            return {
                **state,
                "is_valid": False,
                "retry_count": retry_count,
                "bot_message": "I couldn't find a phone number in that. Please enter just the 10 digits of your phone number.",
                "system_error": {}
            }

        # STEP 2 — Validate using tool
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this phone number: '{clean_phone}'. Use the validate_phone_tool."
        )

        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_phone_tool":
                validation_result = validate_phone_tool.invoke(tool_call["args"])
                break

        # Guard: tool never called
        if validation_result is None:
            validation_result = validate_phone_tool.invoke({"phone": clean_phone})

        # STEP 3 — Success
        if validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=phone input={clean_phone} status=SUCCESS")
            return {
                **state,
                "phone": clean_phone,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }

        # STEP 4 — Validation failed
        error_type = validation_result.get("error_type", "invalid_phone")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=phone input={clean_phone} error={error_type} retry={retry_count}")

        structured_llm = llm.with_structured_output(ErrorResponse)
        error_response = structured_llm.invoke(
            f"You are a friendly contact form assistant. The user was asked for their 10-digit phone number. "
            f"They entered: '{clean_phone}'. "
            f"This failed validation. The specific reason is: {tool_message} "
            f"Write a SHORT, warm reply (1-2 sentences) that: "
            f"1) acknowledges what they typed, "
            f"2) states the exact problem (wrong digit count, contains letters, etc.), "
            f"3) reminds them it must be exactly 10 digits, numbers only, "
            f"4) asks them to try again. "
            f"Do NOT say 'Hi' or 'Hello'. Do NOT greet them again. "
            f"Do NOT sound like this is the first time asking. "
            f"This is retry attempt {retry_count}. "
            f"Return field='phone', error_type='{error_type}', retry_count={retry_count}."
        )

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "bot_message": error_response.message,
            "system_error": {}
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"session_id={session_id} node=validatePhone error={error_msg}")
        return {
            **state,
            "is_valid": False,
            "retry_count": state.get("retry_count", 0) + 1,
            "bot_message": "Sorry, something went wrong. Please try entering your phone number again.",
            "system_error": {
                "node": "validatePhone",
                "error_type": "tool_error",
                "message": error_msg
            }
        }


# ─────────────────────────────────────────────
# NODE 7 — askMessage
# ─────────────────────────────────────────────
def askMessage(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        f"You are a friendly contact form assistant. All details collected. "
        f"Now ask the user to type their message or query for the team. "
        f"Keep it short and warm (1-2 sentences). Do NOT say Hi or Hello again. "
        f"Return field='message' and status='asking'."
    )

    return {
        **state,
        "current_field": "message",
        "bot_message": response.message,
        "system_error": {}
    }


# ─────────────────────────────────────────────
# NODE 8 — saveToDB
# ─────────────────────────────────────────────
def saveToDB(state: ContactState) -> ContactState:
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
        logger.error(f"session_id={session_id} node=saveToDB error={error_msg}")
        return {
            **state,
            "bot_message": "Sorry, we had an issue finalising your details. Please try again.",
            "is_complete": False,
            "system_error": {
                "node": "saveToDB",
                "error_type": "llm_error",
                "message": error_msg
            }
        }


# ─────────────────────────────────────────────
# CONDITIONAL EDGE FUNCTIONS
#
# KEY ARCHITECTURE FIX:
# On retry (is_valid=False), we route back to the validate node — NOT the ask node.
# This means the error message from validateX is shown directly to the user
# without being overwritten by askX generating a fresh greeting-style prompt.
#
# Graph flow on retry:
#   validateName (error, is_valid=False) → [interrupt] → validateName (re-runs with new input)
#
# Graph flow on success:
#   validateName (success, is_valid=True) → askEmail → [interrupt] → validateEmail
# ─────────────────────────────────────────────
def shouldContinueName(state: ContactState) -> str:
    # Success → move to askEmail
    # Failure → stay at validateName (graph will interrupt_before validateName again)
    return "askEmail" if state["is_valid"] else "validateName"


def shouldContinueEmail(state: ContactState) -> str:
    return "askPhone" if state["is_valid"] else "validateEmail"


def shouldContinuePhone(state: ContactState) -> str:
    return "askMessage" if state["is_valid"] else "validatePhone"