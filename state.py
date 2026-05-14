# state.py
from typing import TypedDict
from pydantic import BaseModel


class ContactState(TypedDict):
    session_id: str       # UUID from frontend — links all DB records
    name: str             # collected from user
    email: str            # collected from user
    phone: str            # collected from user
    message: str          # collected from user
    current_field: str    # 'name', 'email', 'phone', 'message'
    retry_count: int      # how many times user retried current field
    is_valid: bool        # True if last validation passed
    validation_error: str   # ← NEW: error message from last failed validation
    final_data: dict      # # complete form data after completeForm
    bot_message: str      # current bot message to return to browser
    is_complete: bool     # set True by completeForm + disable input
    system_error: dict    # crash info: {"node": "...", "error_type": "...", "message": "..."}
                          # empty dict {} if no crash — Flask reads this after invoke()


class BotResponse(BaseModel):
    message: str    # friendly message shown to user in chat
    field: str      # which field is being asked
    status: str     # always 'asking'


class ErrorResponse(BaseModel):
    message: str        # friendly error message shown to user
    field: str          # which field failed
    error_type: str     # what was wrong — logged via logger.warning()
    retry_count: int    # how many times user has tried


class ExtractedName(BaseModel):
    name: str

class ExtractedEmail(BaseModel):
    email: str

class ExtractedPhone(BaseModel):
    phone: str

# add this at the bottom with the other models
class ExtractedDescription(BaseModel):
    description: str
    skipped: bool