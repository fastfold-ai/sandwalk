"""Unit tests for multimodal user content block builder."""

from pathlib import Path

from agent.runner.multimodal_user_message import (
    build_multimodal_user_content,
    extract_multimodal_paths,
)


def test_extract_multimodal_paths():
    text = "Look at @uploads/photo.png and @notes/report.pdf please"
    assert extract_multimodal_paths(text) == [
        "uploads/photo.png",
        "notes/report.pdf",
    ]


def test_extract_paths_with_spaces():
    text = (
        "@uploads/Screenshot 2026-07-16 at 1.18.36 PM.png what's in the image?"
    )
    assert extract_multimodal_paths(text) == [
        "uploads/Screenshot 2026-07-16 at 1.18.36 PM.png"
    ]


def test_non_vision_model_returns_string(tmp_path: Path):
    img = tmp_path / "uploads" / "a.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    prompt = "@uploads/a.png what is this?"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="local",
        model_id="llama3.2",
    )
    assert out == prompt
    assert isinstance(out, str)


def test_image_injects_content_block(tmp_path: Path):
    img = tmp_path / "uploads" / "shot.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    prompt = "@uploads/shot.png describe this"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="anthropic",
        model_id="claude-sonnet-4-5",
    )
    assert isinstance(out, list)
    assert out[0] == {"type": "text", "text": prompt}
    assert out[1]["type"] == "image"
    assert out[1]["mime_type"] == "image/png"
    assert "base64" in out[1]


def test_spaced_filename_injects_for_gemini(tmp_path: Path):
    name = "Screenshot 2026-07-16 at 1.18.36 PM.png"
    img = tmp_path / "uploads" / name
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    prompt = f"@{img.relative_to(tmp_path).as_posix()} what's in the image?"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="google",
        model_id="gemini-3.1-pro-preview",
    )
    assert isinstance(out, list)
    assert out[1]["type"] == "image"


def test_pdf_injects_file_block_with_filename(tmp_path: Path):
    pdf = tmp_path / "uploads" / "doc.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    prompt = "@uploads/doc.pdf summarize"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="openai",
        model_id="gpt-4o",
    )
    assert isinstance(out, list)
    assert out[1]["type"] == "file"
    assert out[1]["mime_type"] == "application/pdf"
    assert out[1]["filename"] == "doc.pdf"


def test_audio_and_video_for_gemini(tmp_path: Path):
    audio = tmp_path / "uploads" / "clip.wav"
    video = tmp_path / "uploads" / "clip.mp4"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"RIFF" + b"\x00" * 12)
    video.write_bytes(b"\x00" * 32)
    prompt = "@uploads/clip.wav @uploads/clip.mp4"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="google",
        model_id="gemini-2.5-flash",
    )
    assert isinstance(out, list)
    kinds = {block["type"] for block in out[1:]}
    assert kinds == {"audio", "video"}


def test_path_traversal_rejected(tmp_path: Path):
    outside = tmp_path.parent / "secret.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    # Craft a path that resolves outside when joined naively.
    prompt = "@../secret.png what?"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="anthropic",
        model_id="claude-sonnet-4-5",
    )
    # Either no match (regex) or rejected resolve → string
    assert isinstance(out, str)


def test_csv_not_injected(tmp_path: Path):
    csv = tmp_path / "uploads" / "data.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    prompt = "@uploads/data.csv analyze"
    out = build_multimodal_user_content(
        prompt,
        workspace_root=tmp_path,
        provider="anthropic",
        model_id="claude-sonnet-4-5",
    )
    assert out == prompt
