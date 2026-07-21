"""Sapphire-side operator identity resolution for gated execution paths."""

import os

from core.settings_manager import settings

OPERATOR_ID_ENV = "SAPPHIRE_OPERATOR_ID"
OPERATOR_ID_SETTING = "OPERATOR_ID"


def validate_operator_id(value):
    if not isinstance(value, str):
        return None

    operator_id = value.strip()
    if not operator_id:
        return None

    return operator_id


def read_operator_id():
    environment_value = validate_operator_id(os.environ.get(OPERATOR_ID_ENV, ""))
    if environment_value:
        return environment_value

    return validate_operator_id(settings.get(OPERATOR_ID_SETTING, ""))


def validate_operator_id_for_save(value):
    """Validate an OPERATOR_ID submitted through settings."""
    if value is None or value == "":
        return True, ""

    if not isinstance(value, str):
        return False, "Operator ID must be text."

    if value != value.strip():
        return False, "Operator ID cannot begin or end with spaces."

    if len(value) > 128:
        return False, "Operator ID must be 128 characters or fewer."

    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False, "Operator ID cannot contain control characters."

    return True, value


def resolve_operator_id(prompt=False, input_fn=None):
    operator_id = read_operator_id()
    if operator_id:
        return operator_id

    if not prompt:
        return None

    if input_fn is None:
        input_fn = input

    return validate_operator_id(input_fn("operator_id: "))
