import core.identity.operator as operator


def test_environment_operator_id_overrides_settings(monkeypatch):
    monkeypatch.setenv(operator.OPERATOR_ID_ENV, " env-operator ")
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "settings-operator")
    assert operator.read_operator_id() == "env-operator"


def test_settings_operator_id_used_when_environment_missing(monkeypatch):
    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: " settings-operator ")
    assert operator.read_operator_id() == "settings-operator"


def test_invalid_environment_value_falls_back_to_settings(monkeypatch):
    monkeypatch.setenv(operator.OPERATOR_ID_ENV, "   ")
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "settings-operator")
    assert operator.read_operator_id() == "settings-operator"


def test_missing_environment_and_settings_fail_closed(monkeypatch):
    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "")
    assert operator.resolve_operator_id(prompt=False) is None


def test_prompt_occurs_only_when_persistent_sources_are_missing(monkeypatch):
    monkeypatch.delenv(operator.OPERATOR_ID_ENV, raising=False)
    monkeypatch.setattr(operator.settings, "get", lambda key, default=None: "")
    prompts = []
    result = operator.resolve_operator_id(
        prompt=True,
        input_fn=lambda prompt: prompts.append(prompt) or " prompted-operator ",
    )
    assert result == "prompted-operator"
    assert prompts == ["operator_id: "]
