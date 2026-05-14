# tools.py
import re
from langchain_core.tools import tool


# ── Blacklist of obvious placeholder/fake names ──
FAKE_NAMES = {
    "full name", "your name", "name here", "first last",
    "firstname lastname", "test", "test name", "fake",
    "user", "username", "enter name", "type name",
    "abc", "xyz", "asdf", "qwerty", "na", "n/a",
    "none", "null", "undefined"
}


@tool
def validate_name_tool(name: str) -> dict:
    """Validate the user's name. Checks for empty, letters only, minimum length."""
    name = name.strip()

    if not name:
        return {"valid": False, "error_type": "empty_name", "message": "Name cannot be empty."}

    if any(char.isdigit() for char in name):
        return {"valid": False, "error_type": "name_has_numbers", "message": "Names cannot contain numbers. Please enter letters only."}

    if len(name) < 2:
        return {"valid": False, "error_type": "name_too_short", "message": "That name is too short. Please enter your full name."}

    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        return {"valid": False, "error_type": "special_characters", "message": "Names can only contain letters, spaces, hyphens, or apostrophes. No other symbols."}

    # ── NEW: placeholder/fake name detection ──
    if name.lower() in FAKE_NAMES:
        return {
            "valid": False,
            "error_type": "placeholder_name",
            "message": f"'{name}' looks like a placeholder, not a real name. Please enter your actual full name."
        }

    # ── NEW: each word must be at least 2 characters ──
    words = name.split()
    if any(len(word) < 2 for word in words):
        return {
            "valid": False,
            "error_type": "word_too_short",
            "message": f"Each part of your name must be at least 2 characters. Please enter your full name."
        }

    # ── NEW: must have at least 2 words (first + last name) ──
    if len(words) < 2:
        return {
            "valid": False,
            "error_type": "single_word_name",
            "message": "Please enter both your first and last name."
        }

    return {"valid": True, "error_type": None, "message": "Name is valid."}


@tool
def validate_email_tool(email: str) -> dict:
    """Validate the user's email address. Checks for proper format."""
    email = email.strip()

    if not email:
        return {"valid": False, "error_type": "empty_email", "message": "You didn't enter an email address."}

    if "@" not in email:
        return {"valid": False, "error_type": "missing_at_symbol", "message": f"'{email}' is missing the @ symbol. A valid email looks like name@example.com."}

    parts = email.split("@")
    if len(parts) != 2 or not parts[0]:
        return {"valid": False, "error_type": "invalid_format", "message": f"'{email}' is not a valid email format. It should look like name@example.com."}

    local = parts[0]   # the part BEFORE @
    domain = parts[1]  # the part AFTER @

    # ── NEW: local part must contain at least one letter ──
    if not any(char.isalpha() for char in local):
        return {
            "valid": False,
            "error_type": "no_letter_before_at",
            "message": f"'{email}' — the part before @ must contain at least one letter. Try something like yourname@gmail.com."
        }

    if "." not in domain:
        return {"valid": False, "error_type": "missing_dot_in_domain", "message": f"The domain part '{domain}' is missing a dot. It should look like gmail.com or yahoo.com."}

    domain_parts = domain.split(".")
    if not domain_parts[0] or not domain_parts[-1]:
        return {"valid": False, "error_type": "invalid_domain", "message": f"'{email}' has an incomplete domain. Try something like name@gmail.com."}

    return {"valid": True, "error_type": None, "message": "Email is valid."}


@tool
def validate_phone_tool(phone: str) -> dict:
    """Validate Indian mobile number. Must be 10 digits starting with 6-9."""
    phone = phone.strip()

    if not phone:
        return {"valid": False, "error_type": "empty_phone", "message": "You didn't enter a phone number."}

    if not phone.isdigit():
        return {"valid": False, "error_type": "contains_non_digits", "message": f"'{phone}' contains characters that are not digits. Please enter numbers only, like 9876543210."}

    if len(phone) != 10:
        return {
            "valid": False,
            "error_type": "wrong_digit_count",
            "message": f"You entered {len(phone)} digits, but a phone number must be exactly 10 digits. Please check and try again.",
        }

    if phone[0] not in "6789":
        return {
            "valid": False,
            "error_type": "invalid_start_digit",
            "message": f"'{phone}' is not a valid Indian mobile number. It must start with 6, 7, 8, or 9.",
        }

    if len(set(phone)) == 1:
        return {
            "valid": False,
            "error_type": "repeated_digits",
            "message": f"'{phone}' looks like a repeated digit number, which is not valid. Please enter your actual phone number.",
        }

    return {"valid": True, "error_type": None, "message": "Phone number is valid."}