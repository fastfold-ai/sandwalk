"""Tests for context-window extraction during model discovery."""

from __future__ import annotations

from unittest.mock import patch

from agent import model_discovery


class TestOllamaTagsContext:
    def test_reads_context_length_from_tag_details(self):
        payload = {
            "models": [
                {
                    "name": "gemma4:12b",
                    "details": {
                        "family": "gemma4",
                        "context_length": 262144,
                    },
                },
                {"name": "old-model", "details": {"family": "llama"}},
            ]
        }
        with patch.object(
            model_discovery, "_request_json", return_value=(payload, None)
        ):
            names, windows, err = model_discovery.fetch_ollama_tags_with_context(
                "http://localhost:11434"
            )
        assert err is None
        assert names == ["gemma4:12b", "old-model"]
        assert windows == {"gemma4:12b": 262144}

    def test_falls_back_to_api_show_when_tags_omit_context(self):
        tags_payload = {
            "models": [
                {"name": "qwen3.6:35b-a3b-mlx-bf16", "details": {"family": "qwen3_5_moe"}},
                {"name": "gemma4:12b", "details": {"context_length": 262144}},
            ]
        }

        def fake_request(url, api_key, *, timeout=10.0, method="GET", body=None):
            if method == "GET":
                return tags_payload, None
            if method == "POST" and body and body.get("model") == "qwen3.6:35b-a3b-mlx-bf16":
                return (
                    {
                        "model_info": {
                            "qwen3_5_moe.context_length": 262144,
                            "qwen3_5_moe.embedding_length": 2048,
                        }
                    },
                    None,
                )
            return None, "unexpected request"

        with patch.object(model_discovery, "_request_json", side_effect=fake_request):
            names, windows, err = model_discovery.fetch_ollama_tags_with_context(
                "http://localhost:11434"
            )
        assert err is None
        assert set(names) == {"gemma4:12b", "qwen3.6:35b-a3b-mlx-bf16"}
        assert windows == {
            "gemma4:12b": 262144,
            "qwen3.6:35b-a3b-mlx-bf16": 262144,
        }


class TestOllamaShowContext:
    def test_reads_context_length_from_model_info(self):
        payload = {
            "model_info": {
                "qwen3_5_moe.context_length": 262144,
            }
        }
        with patch.object(
            model_discovery, "_request_json", return_value=(payload, None)
        ):
            value = model_discovery.fetch_ollama_show_context(
                "http://localhost:11434",
                "qwen3.6:35b-a3b-mlx-bf16",
            )
        assert value == 262144


class TestOpenAIModelsContext:
    def test_reads_max_model_len_and_context_length(self):
        payload = {
            "data": [
                {"id": "qwen-omlx", "max_model_len": 131072},
                {"id": "gguf-unsloth", "context_length": 65536},
                {"id": "no-context"},
            ]
        }
        with patch.object(
            model_discovery, "_request_json", return_value=(payload, None)
        ):
            names, windows, err = (
                model_discovery.fetch_openai_models_with_context(
                    "http://localhost:8000/v1"
                )
            )
        assert err is None
        assert set(names) == {"qwen-omlx", "gguf-unsloth", "no-context"}
        assert windows == {"qwen-omlx": 131072, "gguf-unsloth": 65536}


class TestProbeIncludesWindows:
    def test_probe_returns_context_windows_for_ollama(self):
        payload = {
            "models": [
                {"name": "gemma4:12b", "details": {"context_length": 262144}}
            ]
        }
        with patch.object(
            model_discovery, "_request_json", return_value=(payload, None)
        ):
            probe = model_discovery.probe_compatible_profile(
                base_url="http://localhost:11434",
                backend="ollama",
                api_key=None,
            )
        assert probe["health"] == "healthy"
        assert probe["context_windows"] == {"gemma4:12b": 262144}
