# nodes.py
from langchain_groq import ChatGroq
from state import ContactState, BotResponse, ErrorResponse, ExtractedName, ExtractedEmail, ExtractedPhone
from tools import validate_name_tool, validate_email_tool, validate_phone_tool
from logger import logger
import os

# Initialize LLM — Groq API
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    #model="meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.environ.get("GROQ_API_KEY")
)


# ─────────────────────────────────────────────
# NODE 1 — askName
# ONLY runs at conversation start (entry point).
# On retry, validateName handles the re-ask message directly.
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# NODE 2 — validateName
# Extracts + validates name.
# On failure: writes validation_error to state, routes back to askName.
# askName reads validation_error and generates the error message.
# ─────────────────────────────────────────────
def validateName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("name", "").strip()

    # ── Edge case: empty input ──
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
        # STEP 1 — Extract clean name
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

        # Guard: extraction returned empty
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

        # Guard: tool never called
        if validation_result is None:
            validation_result = validate_name_tool.invoke({"name": clean_name})

        # STEP 3 — Success
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

        # STEP 4 — Failure: write error to state, askName will generate the message
        error_type = validation_result.get("error_type", "unknown_error")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=name input={clean_name} error={error_type} retry={retry_count}")

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": tool_message,   # askName reads this
            "bot_message": "",                   # askName sets this
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


# ─────────────────────────────────────────────
# NODE 3 — askEmail
# ONLY runs after name is successfully validated.
# On retry, validateEmail handles the re-ask message directly.
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# NODE 4 — validateEmail
# On failure: writes validation_error, routes back to askEmail.
# ─────────────────────────────────────────────
def validateEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("email", "").strip()

    # ── Edge case: empty input ──
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
                "validation_error": "I couldn't find an email address in that. Please type just your email (e.g. name@example.com).",
                "bot_message": "",
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
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        # STEP 4 — Failure: write error to state, askEmail will generate the message
        error_type = validation_result.get("error_type", "invalid_format")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=email input={clean_email} error={error_type} retry={retry_count}")

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": tool_message,   # askEmail reads this
            "bot_message": "",                   # askEmail sets this
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


# ─────────────────────────────────────────────
# NODE 5 — askPhone
# First time: ask for phone friendly.
# Retry: show specific error from validation_error, ask again.
# ─────────────────────────────────────────────
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

# ─────────────────────────────────────────────
# NODE 6 — validatePhone
# On failure: writes validation_error, routes back to askPhone.
# ─────────────────────────────────────────────
def validatePhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("phone", "").strip()

    # ── Edge case: empty input ──
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
                "validation_error": "I couldn't find a phone number in that. Please enter just the 10 digits of your phone number.",
                "bot_message": "",
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
                "validation_error": "",
                "bot_message": "",
                "system_error": {}
            }

        # STEP 4 — Failure: write error to state, askPhone will generate the message
        error_type = validation_result.get("error_type", "invalid_phone")
        tool_message = validation_result.get("message", "")
        retry_count = state.get("retry_count", 0) + 1
        logger.warning(f"session_id={session_id} field=phone input={clean_phone} error={error_type} retry={retry_count}")

        return {
            **state,
            "is_valid": False,
            "retry_count": retry_count,
            "validation_error": tool_message,   # askPhone reads this
            "bot_message": "",                   # askPhone sets this
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
    


# ─────────────────────────────────────────────
# NODE 7 — askMessage
# First time: ask for message.
# Retry: show specific validation error.
# ─────────────────────────────────────────────
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
# ─────────────────────────────────────────────
# NODE 8 — validateMessage
# Simple checks only — no LLM extraction, no tool calling needed.
# On failure: writes validation_error, routes back to askMessage.
# ─────────────────────────────────────────────

def validateMessage(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("message", "").strip()

    # ── Check 1: Empty ──
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

    # ── Check 2: Too short ──
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

    # ── Check 3: Too long ──
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

    # ── Success ──
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



# ─────────────────────────────────────────────
# NODE 9 — saveToDB
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
# ─────────────────────────────────────────────
# ── Conditional edge functions (updated to route failures back to ask nodes) ──

def shouldContinueName(state: ContactState) -> str:
    return "askEmail" if state["is_valid"] else "askName"   # was "validateName"


def shouldContinueEmail(state: ContactState) -> str:
    return "askPhone" if state["is_valid"] else "askEmail"  # was "validateEmail"


def shouldContinuePhone(state: ContactState) -> str:
    return "askMessage" if state["is_valid"] else "askPhone" # was "validatePhone"

# ── Conditional edge function ──
def shouldContinueMessage(state: ContactState) -> str:
    return "saveToDB" if state["is_valid"] else "askMessage"