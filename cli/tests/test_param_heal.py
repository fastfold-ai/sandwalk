from agent.model_catalog.param_heal import (
    apply_effort_floor,
    apply_param_heal_from_error,
    empty_heal,
    get_param_heal,
    is_param_healable_error,
    next_param_heal,
)


def test_heal_ladder_and_effort_floor():
    first = next_param_heal(empty_heal())
    assert first["omit_temperature"] is True
    second = next_param_heal(first)
    assert second["omit_require_parameters"] is True
    third = next_param_heal(second)
    assert third["effort_min"] == "low"
    fourth = next_param_heal(third)
    assert fourth["omit_reasoning"] is True
    assert next_param_heal(fourth) is None
    assert apply_effort_floor("none", {"effort_min": "low"}) == "low"
    assert apply_effort_floor("medium", {"effort_min": "low"}) == "medium"


def test_healable_routing_error_not_auth():
    assert is_param_healable_error(
        RuntimeError(
            "No endpoints found that can handle the requested parameters"
        )
    )
    assert is_param_healable_error(
        RuntimeError("Unsupported parameter: temperature")
    )
    assert not is_param_healable_error(RuntimeError("401 Unauthorized api key"))
    assert not is_param_healable_error(RuntimeError("Rate limit 429"))


def test_apply_param_heal_persists(isolated_tmp_config=None):
    class _Cfg:
        def __init__(self):
            self.data = {
                "llm.provider": "openrouter",
                "llm.model": "openai/gpt-6-astra",
                "llm.param_heals": {},
            }
            self.saved = False

        def get(self, key, default=None):
            return self.data.get(key, default)

        def set(self, key, value):
            self.data[key] = value

        def save(self):
            self.saved = True

    cfg = _Cfg()
    exc = RuntimeError("No endpoints found that can handle the requested parameters")
    assert apply_param_heal_from_error(cfg, exc) is True
    heal = get_param_heal(cfg.data["llm.param_heals"], "openrouter", "openai/gpt-6-astra")
    assert heal["omit_temperature"] is True
    assert cfg.saved is True
    assert apply_param_heal_from_error(cfg, RuntimeError("401 invalid api key")) is False
