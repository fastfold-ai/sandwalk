//! Single Whisper artifact: multilingual Base (covers English too).

pub const DEFAULT_MODEL_ID: &str = "multi";
/// Older installs wrote `en` into `stt-active`. That id now maps to the same model.
pub const EN_MODEL_ID: &str = "en";
pub const MULTI_MODEL_ID: &str = DEFAULT_MODEL_ID;

#[derive(Debug, Clone, Copy)]
pub struct SttModelSpec {
    pub id: &'static str,
    pub file: &'static str,
    pub url: &'static str,
    pub bytes: u64,
    pub sha256: &'static str,
    pub name: &'static str,
    /// Whisper decode language. `None` lets the model auto-detect.
    pub language: Option<&'static str>,
}

pub const STT_MODELS: &[SttModelSpec] = &[SttModelSpec {
    id: DEFAULT_MODEL_ID,
    file: super::DEFAULT_MODEL_FILE,
    url: super::DEFAULT_MODEL_URL,
    bytes: super::DEFAULT_MODEL_BYTES,
    sha256: super::DEFAULT_MODEL_SHA256,
    name: "Whisper Base Multilingual (local)",
    language: None,
}];

pub fn stt_model(id: &str) -> Option<&'static SttModelSpec> {
    match id {
        "" | DEFAULT_MODEL_ID | EN_MODEL_ID => STT_MODELS.first(),
        _ => STT_MODELS.iter().find(|model| model.id == id),
    }
}

pub fn stt_model_or_en(id: &str) -> &'static SttModelSpec {
    stt_model(id).unwrap_or(&STT_MODELS[0])
}
