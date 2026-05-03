# nodes.py
from langchain_groq import ChatGroq
from state import ContactState, BotResponse, ErrorResponse, ExtractedName,ExtractedEmail,ExtractedPhone
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
# ─────────────────────────────────────────────
def validateName(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("name", "")
 
    try:
        # STEP 1 — Extract clean name
        structured_llm = llm.with_structured_output(ExtractedName)
        extracted = structured_llm.invoke(
            f"Extract ONLY the person's actual name from this input: '{raw_input}'. "
            f"Remove phrases like 'my name is', 'I am', etc."
        )
        clean_name = extracted.name
        logger.info(f"RAW NAME: {raw_input} | CLEAN NAME: {clean_name}")
 
        # STEP 2 — Validate
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this name: '{clean_name}'. Use the validate_name_tool."
        )
 
        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_name_tool":
                validation_result = validate_name_tool.invoke(tool_call["args"])
                break
 
        # STEP 3 — Success
        if validation_result and validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=name input={clean_name} status=SUCCESS")
            return {
                **state,
                "name": clean_name,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }
 
        # STEP 4 — Validation failed
        else:
            error_type = validation_result.get("error_type", "unknown_error") if validation_result else "unknown_error"
            # ← CHANGED: pull the exact message from the tool so the LLM knows the specific problem
            tool_message = validation_result.get("message", "") if validation_result else ""
            retry_count = state.get("retry_count", 0) + 1
            logger.warning(f"session_id={session_id} field=name input={clean_name} error={error_type} retry={retry_count}")
 
            structured_llm = llm.with_structured_output(ErrorResponse)
            error_response = structured_llm.invoke(
                # ← CHANGED: entire prompt rewritten
                # Old: just said "it is invalid, generate a friendly message"
                # New: gives the LLM the exact problem text so it can relay it naturally,
                #      and explicitly forbids sounding like a first-time greeting
                f"You are a friendly contact form assistant. The user was asked for their full name. "
                f"They entered: '{clean_name}'. "
                f"This failed validation. The specific reason is: {tool_message} "
                f"Write a SHORT, warm reply that: "
                f"1) acknowledges what they typed, "
                f"2) explains the exact problem in plain everyday language, "
                f"3) asks them to try again. "
                f"Do NOT greet them again. Do NOT say 'Hi' or 'Hello'. "
                f"Do NOT sound like you are asking for their name for the first time. "
                f"This is attempt number {retry_count}. "
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
 
# NODE 3 — askEmail
# ─────────────────────────────────────────────
def askEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        f"You are a friendly contact form assistant. The user's name is {state.get('name', 'there')}. "
        f"Ask for their email address in a friendly way. Keep it short. "
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
# ─────────────────────────────────────────────
def validateEmail(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("email", "")
 
    try:
        # STEP 1 — Extract clean email
        structured_llm = llm.with_structured_output(ExtractedEmail)
        extracted = structured_llm.invoke(
            f"Extract ONLY the email address from this input: '{raw_input}'. "
            f"Remove any extra words or sentences."
        )
        clean_email = extracted.email
        logger.info(f"RAW EMAIL: {raw_input} | CLEAN EMAIL: {clean_email}")
 
        # STEP 2 — Validate
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this email: '{clean_email}'. Use the validate_email_tool."
        )
 
        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_email_tool":
                validation_result = validate_email_tool.invoke(tool_call["args"])
                break
 
        # STEP 3 — Success
        if validation_result and validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=email input={clean_email} status=SUCCESS")
            return {
                **state,
                "email": clean_email,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }
 
        # STEP 4 — Validation failed
        else:
            error_type = validation_result.get("error_type", "invalid_format") if validation_result else "invalid_format"
            # ← CHANGED: pull exact tool message
            tool_message = validation_result.get("message", "") if validation_result else ""
            retry_count = state.get("retry_count", 0) + 1
            logger.warning(f"session_id={session_id} field=email input={clean_email} error={error_type} retry={retry_count}")
 
            structured_llm = llm.with_structured_output(ErrorResponse)
            error_response = structured_llm.invoke(
                # ← CHANGED: entire prompt rewritten
                # Old: "it is invalid, generate a friendly message"
                # New: passes exact failure reason, forbids sounding like a fresh ask
                f"You are a friendly contact form assistant. The user was asked for their email address. "
                f"They entered: '{clean_email}'. "
                f"This failed validation. The specific reason is: {tool_message} "
                f"Write a SHORT, warm reply that: "
                f"1) acknowledges what they typed, "
                f"2) explains the exact problem clearly (e.g. missing @, incomplete domain), "
                f"3) gives a quick example of a valid email like name@example.com, "
                f"4) asks them to try again. "
                f"Do NOT greet them again. Do NOT say 'Hi' or 'Hello'. "
                f"Do NOT sound like you are asking for their email for the first time. "
                f"This is attempt number {retry_count}. "
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
# ─────────────────────────────────────────────
def askPhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        "You are a friendly contact form assistant. Ask the user for their 10-digit phone number. "
        "Keep it short and friendly. Return field='phone' and status='asking'."
    )

    return {
        **state,
        "current_field": "phone",
        "bot_message": response.message,
        "system_error": {}
    }


# ─────────────────────────────────────────────
# NODE 6 — validatePhone
# ─────────────────────────────────────────────
def validatePhone(state: ContactState) -> ContactState:
    session_id = state["session_id"]
    raw_input = state.get("phone", "")
 
    try:
        # STEP 1 — Extract clean phone
        structured_llm = llm.with_structured_output(ExtractedPhone)
        extracted = structured_llm.invoke(
            f"Extract ONLY the phone number digits from this input: '{raw_input}'. "
            f"Return digits only, remove spaces, dashes, brackets, or any other characters."
        )
        clean_phone = extracted.phone
        logger.info(f"RAW PHONE: {raw_input} | CLEAN PHONE: {clean_phone}")
 
        # STEP 2 — Validate
        llm_with_tools = llm.bind_tools([validate_name_tool, validate_email_tool, validate_phone_tool])
        tool_response = llm_with_tools.invoke(
            f"Validate this phone number: '{clean_phone}'. Use the validate_phone_tool."
        )
 
        validation_result = None
        for tool_call in tool_response.tool_calls:
            if tool_call["name"] == "validate_phone_tool":
                validation_result = validate_phone_tool.invoke(tool_call["args"])
                break
 
        # STEP 3 — Success
        if validation_result and validation_result.get("valid"):
            logger.info(f"session_id={session_id} field=phone input={clean_phone} status=SUCCESS")
            return {
                **state,
                "phone": clean_phone,
                "is_valid": True,
                "retry_count": 0,
                "system_error": {}
            }
 
        # STEP 4 — Validation failed
        else:
            error_type = validation_result.get("error_type", "invalid_phone") if validation_result else "invalid_phone"
            # ← CHANGED: pull exact tool message — for phone this now includes the digit count
            tool_message = validation_result.get("message", "") if validation_result else ""
            retry_count = state.get("retry_count", 0) + 1
            logger.warning(f"session_id={session_id} field=phone input={clean_phone} error={error_type} retry={retry_count}")
 
            structured_llm = llm.with_structured_output(ErrorResponse)
            error_response = structured_llm.invoke(
                # ← CHANGED: entire prompt rewritten
                # Old: "it is invalid, generate a friendly message"
                # New: passes the exact digit-count failure so the LLM can say
                #      "you entered 8 digits, we need 10" instead of a generic re-ask
                f"You are a friendly contact form assistant. The user was asked for their 10-digit phone number. "
                f"They entered: '{clean_phone}'. "
                f"This failed validation. The specific reason is: {tool_message} "
                f"Write a SHORT, warm reply that: "
                f"1) acknowledges what they typed, "
                f"2) states the exact problem (e.g. wrong number of digits, contains letters), "
                f"3) reminds them it must be exactly 10 digits with numbers only, "
                f"4) asks them to try again. "
                f"Do NOT greet them again. Do NOT say 'Hi' or 'Hello'. "
                f"Do NOT sound like you are asking for their phone number for the first time. "
                f"This is attempt number {retry_count}. "
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

    # Why this node just asks — NOT acknowledges:
    # Graph pauses BEFORE saveToDB (not before askMessage).
    # So askMessage RUNS first, generates "please type your message" prompt,
    # then graph pauses. User types message. Flask resumes into saveToDB.
    # At this point state["message"] is still empty — user hasn't typed yet.
    # saveToDB is where the message is already in state and can be acknowledged.

    structured_llm = llm.with_structured_output(BotResponse)
    response = structured_llm.invoke(
        f"You are a friendly contact form assistant. Phone number collected successfully. "
        f"Now ask the user to type their message or query for the team. "
        f"Keep it short and friendly. Return field='message' and status='asking'."
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

    # By the time saveToDB runs, state["message"] is already filled
    # because Flask did update_state({message: user_input}) before resuming.
    # So we can acknowledge the message AND thank the user here.

    try:
        structured_llm = llm.with_structured_output(BotResponse)
        response = structured_llm.invoke(
            f"You are a friendly contact form assistant. "
            f"The user named {state.get('name', 'there')} has submitted their message: "
            f"'{state.get('message', '')}'. "
            f"Acknowledge their message warmly, thank them for filling out the form, "
            f"and tell them the team will get back to them soon. Keep it warm and concise. "
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
# ─────────────────────────────────────────────
def shouldContinueName(state: ContactState):
    return "askEmail" if state["is_valid"] else "askName"


def shouldContinueEmail(state: ContactState):
    return "askPhone" if state["is_valid"] else "askEmail"


def shouldContinuePhone(state: ContactState):
    return "askMessage" if state["is_valid"] else "askPhone"