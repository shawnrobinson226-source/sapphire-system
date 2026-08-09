"""Operator identity: the lenient resolve/read path vs the strict save path.

read_operator_id / resolve_operator_id use validate_operator_id (LENIENT: only
non-str/empty/whitespace are rejected). Settings saves use
validate_operator_id_for_save (STRICT: also rejects surrounding whitespace,
>128 chars, and control characters). These tests pin exactly what the lenient
path permits that the strict path rejects -- i.e. what happens when a value that
would fail save-validation reaches settings outside the validated save path --
and that both-invalid inputs fail closed to None.
"""

import core.identity.operator as operator


# ---- divergence: value fails strict save but resolves at read time ----

def test_over_128_char_value_rejected_by_save_but_resolved_at_read(monkeypatch):
    long_value = "x" * 200
    ok, msg = operator.validate_operator_id_for_save(long_value)
    assert ok is False
    assert msg == "Operator ID must be 128 characters or fewer."

    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: long_value)
    assert operator.read_operator_id() == long_value
    assert operator.resolve_operator_id(prompt=False) == long_value


def test_control_char_value_rejected_by_save_but_resolved_at_read(monkeypatch):
    value = "op\x01id"  # embedded control char; not whitespace, so not stripped
    ok, msg = operator.validate_operator_id_for_save(value)
    assert ok is False
    assert msg == "Operator ID cannot contain control characters."

    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: value)
    assert operator.read_operator_id() == value
    assert operator.resolve_operator_id(prompt=False) == value


def test_surrounding_space_rejected_by_save_but_read_strips_and_accepts(monkeypatch):
    value = "  op_1  "
    ok, msg = operator.validate_operator_id_for_save(value)
    assert ok is False
    assert msg == "Operator ID cannot begin or end with spaces."

    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: value)
    # Read does not reject; it normalizes by stripping.
    assert operator.read_operator_id() == "op_1"


def test_env_value_is_never_save_validated_at_read(monkeypatch):
    long_value = "y" * 200
    monkeypatch.setenv(operator.OPERATOR_ID_ENV, long_value)
    # Even with a valid settings value, env precedence + lenient read wins.
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "settings-op")
    assert operator.read_operator_id() == long_value


# ---- both sources individually invalid -> fail closed to None ----

def test_both_env_and_settings_whitespace_fail_closed(monkeypatch):
    monkeypatch.setenv(operator.OPERATOR_ID_ENV, "   ")
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "   ")
    assert operator.read_operator_id() is None
    assert operator.resolve_operator_id(prompt=False) is None


def test_env_whitespace_and_settings_non_string_fail_closed(monkeypatch):
    monkeypatch.setenv(operator.OPERATOR_ID_ENV, "   ")
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: 12345)
    assert operator.read_operator_id() is None
    assert operator.resolve_operator_id(prompt=False) is None


def test_env_missing_and_settings_none_fail_closed(monkeypatch):
    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: None)
    assert operator.read_operator_id() is None
    assert operator.resolve_operator_id(prompt=False) is None


def test_prompt_with_invalid_input_fails_closed(monkeypatch):
    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "")
    result = operator.resolve_operator_id(prompt=True, input_fn=lambda _: "   ")
    assert result is None


# ---- direct characterization of the two validators on the same inputs ----

def test_lenient_validator_permits_what_strict_rejects():
    over_128 = "x" * 129
    control = "op\x01id"
    surrounding = "  op  "
    # Strict save rejects all three.
    assert operator.validate_operator_id_for_save(over_128)[0] is False
    assert operator.validate_operator_id_for_save(control)[0] is False
    assert operator.validate_operator_id_for_save(surrounding)[0] is False
    # Lenient accepts: over-128 and control verbatim, surrounding stripped.
    assert operator.validate_operator_id(over_128) == over_128
    assert operator.validate_operator_id(control) == control
    assert operator.validate_operator_id(surrounding) == "op"


def test_both_validators_agree_on_empty_and_whitespace():
    assert operator.validate_operator_id("") is None
    assert operator.validate_operator_id("   ") is None
    assert operator.validate_operator_id(None) is None
    # Save treats "" as an allowed clear but rejects whitespace-only.
    assert operator.validate_operator_id_for_save("") == (True, "")
    assert operator.validate_operator_id_for_save("   ") == (
        False,
        "Operator ID cannot begin or end with spaces.",
    )
