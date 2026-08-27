#!/usr/bin/env python3
"""Install and speak with mlx-audio Chatterbox / Qwen3 for Capy."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


MODELS = {
    "chatterbox": {
        "repo": "mlx-community/chatterbox-multilingual-v3",
        "kind": "chatterbox",
    },
    "qwen3-06": {
        "repo": "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
        "kind": "qwen3",
    },
    "qwen3-17": {
        "repo": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
        "kind": "qwen3",
    },
}

CHATTERBOX_REF_URL = (
    "https://raw.githubusercontent.com/Blaizzy/mlx-audio/main/"
    "examples/voice_prompts/en_woman.wav"
)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def ensure_deps() -> None:
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        raise SystemExit(
            "mlx-audio needs Python 3.10–3.12. "
            f"{sys.executable} is {sys.version.split()[0]}."
        )
    try:
        import huggingface_hub  # noqa: F401
        import mlx_audio  # noqa: F401
    except ImportError:
        try:
            subprocess.check_call(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "mlx-audio",
                    "huggingface_hub",
                    "soundfile",
                ]
            )
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                "Could not install mlx-audio. Use Python 3.10–3.12 "
                "(brew install python@3.12)."
            ) from exc


def ready_path(dest: Path) -> Path:
    return dest / "READY"


class _JsonTqdm:
    """tqdm stand-in. huggingface_hub calls update/refresh/close on this."""

    def __init__(self, *args, **kwargs):
        iterable = args[0] if args else kwargs.get("iterable")
        self.iterable = iterable
        self.n = 0
        self.total = int(kwargs.get("total") or 0)
        self.desc = kwargs.get("desc") or ""
        self.disable = bool(kwargs.get("disable"))
        self._last = 0

    def _emit(self, force=False):
        if self.disable:
            return
        step = max(self.total // 80, 1_000_000) if self.total else 1_000_000
        if not force and self.n - self._last < step and not (
            self.total and self.n >= self.total
        ):
            return
        self._last = self.n
        emit(
            {
                "phase": "download",
                "downloaded": self.n,
                "total": self.total,
                "message": "Downloading model files…",
            }
        )

    def update(self, n=1):
        self.n += int(n or 0)
        self._emit()
        return True

    def refresh(self, *args, **kwargs):
        self._emit(force=True)
        return None

    def close(self):
        self._emit(force=True)
        return None

    def clear(self, *args, **kwargs):
        return None

    def reset(self, total=None):
        if total is not None:
            self.total = int(total or 0)
        self.n = 0
        self._last = 0
        return None

    def display(self, *args, **kwargs):
        self._emit(force=True)
        return None

    def set_description(self, desc=None, *args, **kwargs):
        self.desc = desc or ""
        return None

    def set_description_str(self, desc=None, *args, **kwargs):
        return self.set_description(desc)

    def set_postfix(self, *args, **kwargs):
        return None

    def set_postfix_str(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def unpause(self):
        return None

    def __iter__(self):
        if self.iterable is None:
            return iter(())
        for item in self.iterable:
            yield item
            self.update(1)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()

    def __bool__(self):
        return True


def install(model_id: str, dest: Path) -> None:
    spec = MODELS[model_id]
    dest.mkdir(parents=True, exist_ok=True)
    emit({"phase": "deps", "downloaded": 0, "total": 0, "message": "Installing mlx-audio…"})
    ensure_deps()
    from huggingface_hub import snapshot_download

    emit(
        {
            "phase": "download",
            "downloaded": 0,
            "total": 0,
            "message": "Downloading model files…",
        }
    )
    kwargs = {"repo_id": spec["repo"], "local_dir": str(dest)}
    try:
        snapshot_download(tqdm_class=_JsonTqdm, **kwargs)
    except TypeError:
        snapshot_download(**kwargs)
    if spec["kind"] == "chatterbox":
        ensure_chatterbox_ref(dest)
    ready_path(dest).write_text(spec["repo"] + "\n", encoding="utf-8")
    size = sum(path.stat().st_size for path in dest.rglob("*") if path.is_file())
    emit(
        {
            "phase": "ready",
            "downloaded": size,
            "total": size,
            "message": "Installed",
            "path": str(dest),
        }
    )


def qwen_speaker(voice: str) -> str:
    name = voice.removeprefix("qwen_") if voice.startswith("qwen_") else voice
    return name or "Ryan"


def qwen_language(lang: str, speaker: str) -> str:
    if lang == "zh":
        return "Chinese"
    if lang == "ja":
        return "Japanese"
    if lang == "ko":
        return "Korean"
    if speaker.lower() in {"ryan", "aiden"}:
        return "English"
    return "English" if lang == "en" else "Chinese"


def ensure_chatterbox_ref(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    ref = dest / "ref.wav"
    if ref.is_file() and ref.stat().st_size > 20_000:
        return ref
    with urlopen(CHATTERBOX_REF_URL, timeout=60) as src, ref.open("wb") as dst:
        dst.write(src.read())
    if not ref.is_file() or ref.stat().st_size < 20_000:
        raise SystemExit("Could not download the default Chatterbox voice clip.")
    return ref


def write_pcm_wav(path: Path, samples, sample_rate: int) -> None:
    import numpy as np

    pcm = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1.0, 1.0)
    import wave

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate) or 24000)
        wav.writeframes((pcm * 32767.0).astype("<i2").tobytes())


def collect_audio(results):
    import numpy as np

    chunks = []
    sample_rate = 24000
    for result in results:
        audio = np.array(result.audio)
        if audio.size == 0:
            continue
        chunks.append(audio.reshape(-1))
        sample_rate = getattr(result, "sample_rate", sample_rate) or sample_rate
    if not chunks:
        raise SystemExit("mlx-audio produced no audio")
    return np.concatenate(chunks), sample_rate


def speak(model_id: str, dest: Path, text: str, voice: str, lang: str, out: Path) -> None:
    spec = MODELS[model_id]
    ensure_deps()
    from mlx_audio.tts.utils import load_model

    model_path = str(dest) if ready_path(dest).is_file() else spec["repo"]
    out.parent.mkdir(parents=True, exist_ok=True)
    emit(
        {
            "phase": "loading",
            "message": "Loading model into memory…",
        }
    )
    model = load_model(model_path=model_path)
    emit({"phase": "generating", "message": "Generating speech…"})
    if spec["kind"] == "chatterbox":
        ref = Path(voice) if voice and Path(voice).is_file() else ensure_chatterbox_ref(dest)
        results = model.generate(
            text=text,
            lang_code=lang or "en",
            ref_audio=str(ref),
            verbose=False,
        )
    else:
        speaker = qwen_speaker(voice)
        results = model.generate(
            text=text,
            voice=speaker,
            lang_code=qwen_language(lang, speaker),
            verbose=False,
        )
    samples, sample_rate = collect_audio(results)
    write_pcm_wav(out, samples, sample_rate)
    if not out.is_file():
        raise SystemExit("mlx-audio did not write a wav file")
    emit({"phase": "spoke", "path": str(out)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["probe", "install", "speak"])
    parser.add_argument("--model", default="chatterbox")
    parser.add_argument("--dest", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--voice", default="")
    parser.add_argument("--lang", default="en")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.model not in MODELS:
        raise SystemExit(f"unknown model {args.model}")
    dest = Path(args.dest)
    if args.command == "probe":
        try:
            import mlx_audio  # noqa: F401

            emit({"ok": True, "mlx_audio": True})
        except ImportError:
            emit({"ok": True, "mlx_audio": False})
        return 0
    if args.command == "install":
        install(args.model, dest)
        return 0
    speak(args.model, dest, args.text, args.voice, args.lang, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
