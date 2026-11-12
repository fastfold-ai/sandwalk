"""Generate an image with the provider's image model and save it in the workspace.

Multimodal chat models can *see* pictures. Almost none of them *draw* one
unless a dedicated image tool calls an image model. This tool is that call:
OpenAI's Responses image tool, OpenRouter's Image API, or Gemini's
generateContent endpoint. The bytes land in the session workspace so
the transcript can preview the file.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from tools import registry

_IMAGE_MARKERS = ("image", "flux", "dall-e", "gpt-image", "recraft", "ideogram", "banana")

# Chat models on OpenRouter rarely accept image output. The same OpenRouter
# key can still draw through the Image API. Flux 3 Klein is a current,
# per-image model at about a cent for a 1K picture.
DEFAULT_OPENROUTER_IMAGE_MODEL = "black-forest-labs/flux-3-image-klein"
# Gemini chat models (Flash, Pro, Argon) see images but do not draw. Nano
# Banana 2 Lite is the current image model on the same Gemini key.
DEFAULT_GOOGLE_IMAGE_MODEL = "gemini-3.1-flash-lite-image"


def looks_like_image_model(model_id: str | None) -> bool:
    value = str(model_id or "").strip().lower()
    return any(marker in value for marker in _IMAGE_MARKERS)


def resolve_image_route(
    provider: str | None,
    *,
    chat_model: str | None = None,
    image_model: str | None = None,
    has_credential: bool = False,
) -> tuple[str, str] | None:
    """Pick ``(backend, model)`` for image generation.

    Only the provider of the model selected in the chat is used. A key saved
    for some other provider is not a fallback. ``image_model`` is an explicit
    override. On OpenRouter, a chat model that cannot draw still uses the
    Image API on that same key, with ``DEFAULT_OPENROUTER_IMAGE_MODEL`` unless
    the selected model is itself an image model.
    """
    if not has_credential:
        return None
    provider_norm = str(provider or "").strip().lower()
    if provider_norm not in {"openai", "openai-chatgpt", "openrouter", "google"}:
        return None
    explicit = str(image_model or "").strip()
    selected = str(chat_model or "").strip()
    if provider_norm == "openrouter":
        if explicit:
            model = explicit
        elif looks_like_image_model(selected):
            model = selected
        else:
            model = DEFAULT_OPENROUTER_IMAGE_MODEL
        return provider_norm, model
    if provider_norm == "google":
        if explicit:
            model = explicit
        elif looks_like_image_model(selected):
            model = selected
        else:
            model = DEFAULT_GOOGLE_IMAGE_MODEL
        return provider_norm, model
    model = explicit or selected
    if not model:
        return None
    return provider_norm, model


def decode_image_payload(raw: str) -> tuple[bytes, str]:
    """Decode a raw base64 string or a ``data:image/...;base64,`` URL."""
    text = str(raw or "").strip()
    mime = "image/png"
    if text.startswith("data:"):
        header, _, body = text.partition(",")
        mime_part = header[5:].split(";", 1)[0].strip()
        if mime_part.startswith("image/"):
            mime = mime_part
        text = body
    try:
        data = base64.b64decode(text, validate=True)
    except binascii.Error as exc:
        raise ValueError("image payload was not valid base64") from exc
    if not data:
        raise ValueError("image payload was empty")
    return data, mime


def parse_responses_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    """Read a Responses API ``image_generation_call`` result."""
    output = payload.get("output")
    if not isinstance(output, list):
        raise ValueError("Responses API image response had no output")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "image_generation_call":
            continue
        result = item.get("result")
        if isinstance(result, str) and result.strip():
            return decode_image_payload(result)
    raise ValueError("Responses API image response contained no image")


def parse_openai_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("OpenAI image response had no data")
    item = data[0]
    encoded = item.get("b64_json") or item.get("b64")
    if not isinstance(encoded, str) or not encoded.strip():
        url = item.get("url")
        raise ValueError(
            "OpenAI image response had no base64 image"
            + (f" (url only: {url})" if isinstance(url, str) else "")
        )
    data, mime = decode_image_payload(encoded)
    media_type = item.get("media_type")
    if isinstance(media_type, str) and media_type.startswith("image/"):
        return data, media_type
    return data, mime


def parse_openrouter_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("OpenRouter image response had no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenRouter image response had no message")
    candidates: list[str] = []
    images = message.get("images")
    if isinstance(images, list):
        for image in images:
            if not isinstance(image, dict):
                continue
            image_url = image.get("image_url")
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                candidates.append(image_url["url"])
            elif isinstance(image_url, str):
                candidates.append(image_url)
            elif isinstance(image.get("url"), str):
                candidates.append(image["url"])
    content = message.get("content")
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            image_url = block.get("image_url")
            if isinstance(image_url, dict) and isinstance(image_url.get("url"), str):
                candidates.append(image_url["url"])
            elif isinstance(block.get("url"), str) and str(block.get("type") or "") in {
                "image",
                "image_url",
            }:
                candidates.append(block["url"])
    if not candidates:
        raise ValueError("OpenRouter image response contained no image")
    return decode_image_payload(candidates[0])


def parse_gemini_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Gemini image response had no candidates")
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            continue
        for part in parts:
            inline = part.get("inlineData") if isinstance(part, dict) else None
            if not isinstance(inline, dict):
                inline = part.get("inline_data") if isinstance(part, dict) else None
            if not isinstance(inline, dict):
                continue
            encoded = inline.get("data")
            if isinstance(encoded, str) and encoded.strip():
                mime = str(inline.get("mimeType") or inline.get("mime_type") or "image/png")
                data, decoded_mime = decode_image_payload(encoded)
                return data, mime if mime.startswith("image/") else decoded_mime
    raise ValueError("Gemini image response contained no image")


def _suffix_for_mime(mime: str) -> str:
    if "jpeg" in mime or mime.endswith("/jpg"):
        return ".jpg"
    if "webp" in mime:
        return ".webp"
    return ".png"


def _slug(prompt: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")
    words = words[:40].strip("-") or "image"
    return f"{words}-{uuid.uuid4().hex[:8]}"


def save_workspace_image(
    data: bytes,
    *,
    mime: str,
    prompt: str,
    workspace: str | None,
    filename: str | None = None,
) -> Path | None:
    root = str(workspace or "").strip()
    if not root:
        return None
    folder = Path(root).expanduser() / "artifacts" / "images"
    folder.mkdir(parents=True, exist_ok=True)
    requested = str(filename or "").strip()
    if requested:
        name = Path(requested).name
        if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            name = f"{name}{_suffix_for_mime(mime)}"
    else:
        name = f"{_slug(prompt)}{_suffix_for_mime(mime)}"
    path = folder / name
    path.write_bytes(data)
    return path


def _workspace_from_session(session: Any) -> str | None:
    env = os.environ.get("SANDWALK_SESSION_WORKSPACE")
    if env and env.strip():
        return env.strip()
    for attr in ("workspace_path", "workspacePath"):
        value = getattr(session, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _credential(session: Any, provider: str) -> str | None:
    """Bearer for the selected provider only."""
    provider_norm = str(provider or "").strip().lower()
    if provider_norm == "openai-chatgpt":
        try:
            from agent.config import chatgpt_auth

            if not chatgpt_auth.is_connected():
                return None
            token = chatgpt_auth.access_token()
        except Exception:  # noqa: BLE001
            return None
        return token.strip() if isinstance(token, str) and token.strip() else None
    config = getattr(session, "config", None)
    if config is None or not hasattr(config, "llm_api_key"):
        return None
    try:
        key = config.llm_api_key(provider_norm)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def _post_json(url: str, *, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=120.0)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"image request failed: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text.strip().replace("\n", " ")[:300]
        raise RuntimeError(f"image request failed ({response.status_code}): {detail}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("image request returned a non-object response")
    return payload


def image_from_responses_event(event: dict[str, Any]) -> tuple[bytes, str] | None:
    """Pull a finished image out of one Responses stream event, if it has one."""
    candidates: list[dict[str, Any]] = []
    item = event.get("item")
    if isinstance(item, dict):
        candidates.append(item)
    response = event.get("response")
    output = response.get("output") if isinstance(response, dict) else None
    if isinstance(output, list):
        candidates.extend(part for part in output if isinstance(part, dict))
    if event.get("type") == "image_generation_call":
        candidates.append(event)
    for candidate in candidates:
        if candidate.get("type") != "image_generation_call":
            continue
        result = candidate.get("result")
        if isinstance(result, str) and result.strip():
            return decode_image_payload(result)
    return None


def _responses_image(api_key: str, model: str, prompt: str) -> tuple[bytes, str]:
    """ChatGPT plan rejects a non-streaming Responses call."""
    body = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        "tools": [{"type": "image_generation"}],
        "tool_choice": {"type": "image_generation"},
        "store": False,
        "stream": True,
    }
    try:
        with httpx.stream(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
            timeout=180.0,
        ) as response:
            if response.status_code >= 400:
                detail = response.read().decode("utf-8", "replace").strip().replace("\n", " ")[:300]
                raise RuntimeError(f"image request failed ({response.status_code}): {detail}")
            found: tuple[bytes, str] | None = None
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    event = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    found = image_from_responses_event(event) or found
    except httpx.HTTPError as exc:
        raise RuntimeError(f"image request failed: {exc}") from exc
    if found is None:
        raise RuntimeError("image request finished without an image")
    return found


def _generate_bytes(backend: str, model: str, prompt: str, api_key: str) -> tuple[bytes, str]:
    if backend in {"openai", "openai-chatgpt"}:
        # The selected GPT model draws through the Responses image tool.
        # ChatGPT plan and an OpenAI API key both authenticate this call.
        return _responses_image(api_key, model, prompt)
    if backend == "openrouter":
        from agent.deepagents_runtime.openrouter_attribution import (
            openrouter_attribution_headers,
        )

        payload = _post_json(
            "https://openrouter.ai/api/v1/images",
            headers={
                "Authorization": f"Bearer {api_key}",
                **openrouter_attribution_headers(),
            },
            body={"model": model, "prompt": prompt},
        )
        return parse_openai_image(payload)
    if backend == "google":
        payload = _post_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key},
            body={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
            },
        )
        return parse_gemini_image(payload)
    raise RuntimeError(f"unsupported image backend: {backend}")


@registry.register(
    name="image.generate",
    description=(
        "Generate a picture from a text prompt with the provider's image model and save it "
        "in the session workspace. Use this for illustrations, photos, logos, and other "
        "images the user asked you to create. Keep using run_python or shell scripts for "
        "plots, charts, and figures computed from data. Being able to view an image is not "
        "the same as generating one; call this tool for real image generation."
    ),
    category="image",
    parameters={
        "prompt": "What the image should show. Be specific about subject, style, and composition.",
        "filename": "Optional file name, such as capybara.png. Saved under artifacts/images/.",
    },
    usage_guide=(
        "Use for generated pictures. Do not use it for matplotlib, seaborn, or other "
        "data plots; those stay on run_python. Draws with the selected model's own "
        "provider and does not switch to another provider's key. On OpenRouter "
        "and Gemini, a chat model that cannot draw uses that provider's image "
        "model on the same key."
    ),
)
def generate_image(
    prompt: str,
    filename: str | None = None,
    _session=None,
    **_kwargs,
) -> dict:
    """Generate one image and return its workspace path plus the raw bytes."""
    text = str(prompt or "").strip()
    if not text:
        return {"summary": "image.generate needs a prompt.", "error": "missing_prompt"}

    config = getattr(_session, "config", None)
    provider = ""
    chat_model = ""
    image_model = ""
    if config is not None and hasattr(config, "get"):
        provider = str(config.get("llm.provider") or "")
        chat_model = str(config.get("llm.model") or "")
        image_model = str(config.get("llm.image_model") or "")
    credential = _credential(_session, provider)
    route = resolve_image_route(
        provider,
        chat_model=chat_model,
        image_model=image_model,
        has_credential=bool(credential),
    )
    if route is None:
        label = f"{provider}/{chat_model}".strip("/") or "the selected model"
        return {
            "summary": (
                f"{label} cannot generate images from this provider. "
                "Image generation stays on the model selected in the chat and does not "
                "use another provider's key. Plots and charts still go through run_python."
            ),
            "error": "no_image_provider",
        }
    backend, model = route
    try:
        data, mime = _generate_bytes(backend, model, text, credential or "")
    except (RuntimeError, ValueError) as exc:
        return {"summary": str(exc), "error": "image_request_failed", "model": model}

    path = save_workspace_image(
        data,
        mime=mime,
        prompt=text,
        workspace=_workspace_from_session(_session),
        filename=filename if isinstance(filename, str) else None,
    )
    summary = f"Generated an image with {model}."
    if path is not None:
        summary += f" Saved to {path}."
    return {
        "summary": summary,
        "path": str(path) if path is not None else None,
        "model": model,
        "mime": mime,
        "image_base64": base64.b64encode(data).decode("ascii"),
        "image_mime": mime,
    }
