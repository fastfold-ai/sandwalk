//! Installable Whisper artifacts. English stays the default; multilingual is opt-in.

pub const EN_MODEL_ID: &str = "en";
pub const MULTI_MODEL_ID: &str = "multi";

#[derive(Debug, Clone, Copy)]
pub struct SttModelSpec {
    pub id: &'static str,
    pub file: &'static str,
    pub url: &'static str,
    pub bytes: u64,
    pub sha256: &'static str,
    pub name: &'static str,
    /// Whisper decode language. `None` lets the multilingual model auto-detect.
    pub language: Option<&'static str>,
}

pub const STT_MODELS: &[SttModelSpec] = &[
    SttModelSpec {
        id: EN_MODEL_ID,
        file: super::DEFAULT_MODEL_FILE,
        url: super::DEFAULT_MODEL_URL,
        bytes: super::DEFAULT_MODEL_BYTES,
        sha256: super::DEFAULT_MODEL_SHA256,
        name: "Whisper Base English (local)",
        language: Some("en"),
    },
    SttModelSpec {
        id: MULTI_MODEL_ID,
        file: "ggml-base.bin",
        url: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
        bytes: 147_951_465,
        sha256: "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
        name: "Whisper Base Multilingual (local)",
        language: None,
    },
];

pub fn stt_model(id: &str) -> Option<&'static SttModelSpec> {
    STT_MODELS.iter().find(|model| model.id == id)
}

pub fn stt_model_or_en(id: &str) -> &'static SttModelSpec {
    stt_model(id).unwrap_or(&STT_MODELS[0])
}
