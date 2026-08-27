//! Installable Kokoro ONNX qualities. Same 82M voices; precision is the tradeoff.

pub const DEFAULT_MODEL_ID: &str = "fp32";
pub const ACTIVE_MODEL_FILE: &str = "tts-active";

#[derive(Debug, Clone, Copy)]
pub struct TtsModelSpec {
    pub id: &'static str,
    pub file: &'static str,
    pub url: &'static str,
    pub bytes: u64,
    pub sha256: &'static str,
    pub name: &'static str,
    pub quality: &'static str,
}

pub const TTS_MODELS: &[TtsModelSpec] = &[
    TtsModelSpec {
        id: "fp32",
        file: "model.onnx",
        url: "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model.onnx",
        bytes: 325_532_232,
        sha256: "8fbea51ea711f2af382e88c833d9e288c6dc82ce5e98421ea61c058ce21a34cb",
        name: "Kokoro 82M · Best",
        quality: "FP32 · highest quality",
    },
    TtsModelSpec {
        id: "fp16",
        file: "model_fp16.onnx",
        url: "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model_fp16.onnx",
        bytes: 163_234_740,
        sha256: "ba4527a874b42b21e35f468c10d326fdff3c7fc8cac1f85e9eb6c0dfc35c334a",
        name: "Kokoro 82M · Clear",
        quality: "FP16 · recommended",
    },
    TtsModelSpec {
        id: "q8",
        file: "model_q8f16.onnx",
        url: "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model_q8f16.onnx",
        bytes: 86_033_585,
        sha256: "04c658aec1b6008857c2ad10f8c589d4180d0ec427e7e6118ceb487e215c3cd0",
        name: "Kokoro 82M · Fast",
        quality: "Q8 · smallest",
    },
];

pub const MLX_MODELS: &[TtsModelSpec] = &[
    TtsModelSpec {
        id: "chatterbox",
        file: "READY",
        url: "mlx-community/chatterbox-multilingual-v3",
        bytes: 2_710_000_000,
        sha256: "",
        name: "Chatterbox · Multilingual v3",
        quality: "MLX · 23 languages · best English",
    },
    TtsModelSpec {
        id: "qwen3-06",
        file: "READY",
        url: "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit",
        bytes: 650_000_000,
        sha256: "",
        name: "Qwen3-TTS · 0.6B",
        quality: "MLX · EN/ZH/JA/KO · faster",
    },
    TtsModelSpec {
        id: "qwen3-17",
        file: "READY",
        url: "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
        bytes: 1_800_000_000,
        sha256: "",
        name: "Qwen3-TTS · 1.7B",
        quality: "MLX · EN/ZH/JA/KO · richer",
    },
];

pub fn is_mlx_model(id: &str) -> bool {
    MLX_MODELS.iter().any(|model| model.id == id)
}

pub fn tts_model(id: &str) -> Option<&'static TtsModelSpec> {
    TTS_MODELS
        .iter()
        .chain(MLX_MODELS.iter())
        .find(|model| model.id == id)
}

pub fn tts_model_or_default(id: &str) -> &'static TtsModelSpec {
    tts_model(id).unwrap_or(&TTS_MODELS[0])
}

pub fn mlx_supported() -> bool {
    cfg!(all(target_os = "macos", target_arch = "aarch64"))
}
