# tools.py
import re
from langchain_core.tools import tool


@tool
def validate_name_tool(name: str) -> dict:
    """Validate the user's name. Checks for empty, letters only, minimum length."""
    name = name.strip()

    if not name:
        return {"valid": False, "error_type": "empty_name", "message": "Name cannot be empty."}

    if any(char.isdigit() for char in name):
        return {"valid": False, "error_type": "name_has_numbers", "message": "Name should not contain numbers."}

    if len(name) < 2:
        return {"valid": False, "error_type": "name_too_short", "message": "Name is too short."}

    if not re.match(r"^[a-zA-Z\s]+$", name):
        return {"valid": False, "error_type": "special_characters", "message": "Name should only contain letters and spaces."}

    return {"valid": True, "error_type": None, "message": "Name is valid."}


@tool
def validate_email_tool(email: str) -> dict:
    """Validate the user's email address. Checks for proper format."""
    email = email.strip()

    if not email:
        return {"valid": False, "error_type": "empty_email", "message": "Email cannot be empty."}

    if "@" not in email:
        return {"valid": False, "error_type": "missing_at", "message": "Email must contain @ symbol."}

    parts = email.split("@")
    if len(parts) != 2 or not parts[0]:
        return {"valid": False, "error_type": "invalid_format", "message": "Invalid email format."}

    domain = parts[1]
    if "." not in domain:
        return {"valid": False, "error_type": "missing_dot", "message": "Email domain must contain a dot."}

    domain_parts = domain.split(".")
    if not domain_parts[0] or not domain_parts[-1]:
        return {"valid": False, "error_type": "invalid_format", "message": "Invalid email format."}

    return {"valid": True, "error_type": None, "message": "Email is valid."}


@tool
def validate_phone_tool(phone: str) -> dict:
    """Validate the user's phone number. Must be exactly 10 digits."""
    phone = phone.strip()

    if not phone:
        return {"valid": False, "error_type": "empty_phone", "message": "Phone number cannot be empty."}

    if not phone.isdigit():
        return {"valid": False, "error_type": "not_digits", "message": "Phone number must contain only digits."}

    if len(phone) != 10:
        return {"valid": False, "error_type": "wrong_length", "message": "Phone number must be exactly 10 digits."}

    return {"valid": True, "error_type": None, "message": "Phone number is valid."}