"""Banner model/provider line matches compose meta styling."""

from agent.config import Config
from cli.banner_support import banner_model_provider_markup


def test_banner_model_provider_shows_label_not_raw_id():
    cfg = Config(
        data={
            "llm.provider": "opencode",
            "llm.model": "kimi-k3",
        }
    )
    markup = banner_model_provider_markup(cfg)
    assert markup is not None
    assert "Kimi K3" in markup
    assert "OpenCode Zen" in markup
    assert "kimi-k3" not in markup


def test_banner_model_provider_moonshot_native():
    cfg = Config(
        data={
            "llm.provider": "moonshot",
            "llm.model": "kimi-k3",
        }
    )
    markup = banner_model_provider_markup(cfg)
    assert markup is not None
    assert "Kimi K3" in markup
    assert "Kimi" in markup
