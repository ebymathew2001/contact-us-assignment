# tests/test_complete_form.py
import os
os.environ["GROQ_API_KEY"] = "test-fake-key"  # ← set before any imports

import pytest
from unittest.mock import MagicMock, patch


def make_state():
    return {
        "session_id": "test-session-123",
        "name": "Eby Mathew",
        "email": "eby@example.com",
        "phone": "9876543210",
        "message": "I need help with my account.",
        "current_field": "message",
        "retry_count": 0,
        "is_valid": True,
        "validation_error": "",
        "final_data": {},
        "bot_message": "",
        "is_complete": False,
        "system_error": {}
    }


def test_is_complete_set_true_on_happy_path(mocker):
    mock_response = MagicMock()
    mock_response.message = "Thank you Eby! We will get back to you soon."

    mocker.patch(
        "nodes.complete_form.llm.with_structured_output",
        return_value=MagicMock(invoke=MagicMock(return_value=mock_response))
    )

    from nodes.complete_form import completeForm
    result = completeForm(make_state())
    assert result["is_complete"] is True


def test_is_complete_false_on_llm_error(mocker):
    mocker.patch(
        "nodes.complete_form.llm.with_structured_output",
        side_effect=Exception("LLM timeout")
    )

    from nodes.complete_form import completeForm
    result = completeForm(make_state())
    assert result["is_complete"] is False
    assert result["system_error"]["node"] == "completeForm"