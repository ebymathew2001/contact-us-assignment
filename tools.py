# tools.py
import re
from langchain_core.tools import tool


@tool
def validate_name_tool(name: str) -> dict:
    """Validate the user's name. Checks for empty, letters only, minimum length."""
    name = name.strip()

    if not name:
        return {"valid": False, "error_type": "empty_name", "message": "Name cannot be empty."}  # ← CHANGED: was generic

    if any(char.isdigit() for char in name):
        return {"valid": False, "error_type": "name_has_numbers", "message": "Names cannot contain numbers. Please enter letters only."}  # ← CHANGED: message more specific

    if len(name) < 2:
        return {"valid": False, "error_type": "name_too_short", "message": "That name is too short. Please enter your full name."}  # ← CHANGED: message more specific

    if not re.match(r"^[a-zA-Z\s]+$", name):
        return {"valid": False, "error_type": "special_characters", "message": "Names can only contain letters and spaces. No symbols or punctuation."}  # ← CHANGED: message more specific

    return {"valid": True, "error_type": None, "message": "Name is valid."}


@tool
def validate_email_tool(email: str) -> dict:
    """Validate the user's email address. Checks for proper format."""
    email = email.strip()

    if not email:
        return {"valid": False, "error_type": "empty_email", "message": "You didn't enter an email address."}  # ← CHANGED: more direct

    if "@" not in email:
        return {"valid": False, "error_type": "missing_at_symbol", "message": f"'{email}' is missing the @ symbol. A valid email looks like name@example.com."}  # ← CHANGED: shows what they typed + example

    parts = email.split("@")
    if len(parts) != 2 or not parts[0]:
        return {"valid": False, "error_type": "invalid_format", "message": f"'{email}' is not a valid email format. It should look like name@example.com."}  # ← CHANGED: shows what they typed

    domain = parts[1]
    if "." not in domain:
        return {"valid": False, "error_type": "missing_dot_in_domain", "message": f"The domain part '{domain}' is missing a dot. It should look like gmail.com or yahoo.com."}  # ← CHANGED: explains domain part specifically

    domain_parts = domain.split(".")
    if not domain_parts[0] or not domain_parts[-1]:
        return {"valid": False, "error_type": "invalid_domain", "message": f"'{email}' has an incomplete domain. Try something like name@gmail.com."}  # ← CHANGED: more specific

    return {"valid": True, "error_type": None, "message": "Email is valid."}


@tool
def validate_phone_tool(phone: str) -> dict:
    """Validate the user's phone number. Must be exactly 10 digits."""
    phone = phone.strip()

    if not phone:
        return {"valid": False, "error_type": "empty_phone", "message": "You didn't enter a phone number."}  # ← CHANGED: more direct

    if not phone.isdigit():
        return {"valid": False, "error_type": "contains_non_digits", "message": f"'{phone}' contains characters that are not digits. Please enter numbers only, like 9876543210."}  # ← CHANGED: shows input + example

    if len(phone) != 10:
        return {  # ← CHANGED: entire block — now tells them exactly how many digits they gave
            "valid": False,
            "error_type": "wrong_digit_count",
            "message": f"You entered {len(phone)} digits, but a phone number must be exactly 10 digits. Please check and try again.",
        }

    return {"valid": True, "error_type": None, "message": "Phone number is valid."}