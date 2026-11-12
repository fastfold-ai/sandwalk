"""Image generation routing and response parsing. No network."""

from __future__ import annotations

import base64

from tools.image_generate import (
    DEFAULT_GOOGLE_IMAGE_MODEL,
    DEFAULT_OPENROUTER_IMAGE_MODEL,
    decode_image_payload,
    image_from_responses_event,
    looks_like_image_model,
    parse_gemini_image,
    parse_openai_image,
    parse_openrouter_image,
    parse_responses_image,
    resolve_image_route,
    save_workspace_image,
)


def test_openrouter_chat_model_uses_the_default_image_model():
    route = resolve_image_route(
        "openrouter",
        chat_model="anthropic/claude-sonnet-5",
        has_credential=True,
    )
    assert route == ("openrouter", DEFAULT_OPENROUTER_IMAGE_MODEL)


def test_openrouter_image_chat_model_draws_itself():
    route = resolve_image_route(
        "openrouter",
        chat_model="google/gemini-3.1-flash-image",
        has_credential=True,
    )
    assert route == ("openrouter", "google/gemini-3.1-flash-image")


def test_google_chat_model_uses_the_gemini_image_model():
    route = resolve_image_route(
        "google",
        chat_model="gemini-3.5-flash",
        has_credential=True,
    )
    assert route == ("google", DEFAULT_GOOGLE_IMAGE_MODEL)


def test_google_image_model_draws_itself():
    route = resolve_image_route(
        "google",
        chat_model="gemini-3.1-flash-image",
        has_credential=True,
    )
    assert route == ("google", "gemini-3.1-flash-image")


def test_openrouter_image_model_override():
    route = resolve_image_route(
        "openrouter",
        chat_model="anthropic/claude-sonnet-5",
        image_model="openai/gpt-image-1-mini",
        has_credential=True,
    )
    assert route == ("openrouter", "openai/gpt-image-1-mini")


def test_route_uses_the_chatgpt_plan_model():
    route = resolve_image_route(
        "openai-chatgpt",
        chat_model="gpt-5.6-sol",
        has_credential=True,
    )
    assert route == ("openai-chatgpt", "gpt-5.6-sol")


def test_route_does_not_hop_to_another_provider():
    assert (
        resolve_image_route(
            "anthropic",
            chat_model="claude-sonnet-5",
            has_credential=True,
        )
        is None
    )


def test_route_is_none_without_a_credential():
    assert (
        resolve_image_route(
            "openrouter",
            chat_model="google/gemini-2.5-flash-image",
            has_credential=False,
        )
        is None
    )


def test_image_from_responses_stream_event():
    raw = base64.b64encode(b"png").decode()
    found = image_from_responses_event(
        {
            "type": "response.output_item.done",
            "item": {"type": "image_generation_call", "result": raw},
        }
    )
    assert found is not None
    assert found[0] == b"png"


def test_parse_responses_image_call():
    raw = base64.b64encode(b"png").decode()
    data, mime = parse_responses_image(
        {"output": [{"type": "image_generation_call", "result": raw}]}
    )
    assert data == b"png"
    assert mime == "image/png"


def test_looks_like_image_model():
    assert looks_like_image_model("google/gemini-2.5-flash-image")
    assert not looks_like_image_model("google/gemini-2.5-flash")


def test_parse_openai_b64():
    raw = base64.b64encode(b"png").decode()
    data, mime = parse_openai_image({"data": [{"b64_json": raw}]})
    assert data == b"png"
    assert mime == "image/png"


def test_parse_openrouter_images_api_media_type():
    raw = base64.b64encode(b"webp").decode()
    data, mime = parse_openai_image(
        {"data": [{"b64_json": raw, "media_type": "image/webp"}]}
    )
    assert data == b"webp"
    assert mime == "image/webp"


def test_parse_openrouter_images_array():
    url = "data:image/webp;base64," + base64.b64encode(b"webp").decode()
    data, mime = parse_openrouter_image(
        {"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}
    )
    assert data == b"webp"
    assert mime == "image/webp"


def test_parse_gemini_inline_data():
    raw = base64.b64encode(b"jpeg").decode()
    data, mime = parse_gemini_image(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"inlineData": {"mimeType": "image/jpeg", "data": raw}}]
                    }
                }
            ]
        }
    )
    assert data == b"jpeg"
    assert mime == "image/jpeg"


def test_decode_rejects_empty():
    try:
        decode_image_payload("")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_save_workspace_image(tmp_path):
    path = save_workspace_image(
        b"hello",
        mime="image/png",
        prompt="red circle",
        workspace=str(tmp_path),
        filename="circle.png",
    )
    assert path is not None
    assert path.read_bytes() == b"hello"
    assert path.parent.name == "images"
