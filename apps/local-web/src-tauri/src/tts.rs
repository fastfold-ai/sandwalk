//! Local Kokoro TTS — Tauri commands over the `sandwalk-tts` crate.

use crate::dictation::models_dir;
use sandwalk_tts::{
    DownloadProgress, SpeechAudio, TtsEngine, TtsModelStatus, TtsStatus, VoiceInfo,
};
use serde::Serialize;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Clone, Serialize)]
pub struct VoiceTtsStatus {
    pub model_installed: bool,
    pub model_verified: bool,
    pub download_in_progress: bool,
    pub model_name: &'static str,
    pub model_bytes: u64,
    pub active_model: String,
    pub models: Vec<TtsModelStatus>,
    pub voice_count: usize,
    pub voices_installed: usize,
    pub voices: Vec<VoiceInfo>,
    pub supported: bool,
}

fn tts_status(engine: &TtsEngine) -> VoiceTtsStatus {
    let status: TtsStatus = engine.status();
    let voices = sandwalk_tts::voices_for_model(&status.active_model).to_vec();
    VoiceTtsStatus {
        model_installed: status.model_installed,
        model_verified: status.model_verified,
        download_in_progress: status.download_in_progress,
        model_name: status.model_name,
        model_bytes: status.model_bytes,
        active_model: status.active_model,
        models: status.models,
        voice_count: status.voice_count,
        voices_installed: status.voices_installed,
        voices,
        supported: true,
    }
}

pub fn manage_tts(app: &mut tauri::App) {
    let _ = std::fs::create_dir_all(models_dir());
    app.manage(Arc::new(TtsEngine::new(models_dir())));
}

#[tauri::command]
pub fn get_tts_status(state: State<Arc<TtsEngine>>) -> VoiceTtsStatus {
    tts_status(&state)
}

#[tauri::command]
pub async fn download_tts_model(
    app: AppHandle,
    state: State<'_, Arc<TtsEngine>>,
    model_id: Option<String>,
) -> Result<VoiceTtsStatus, String> {
    let engine = state.inner().clone();
    let model_id = model_id.unwrap_or_else(|| sandwalk_tts::DEFAULT_MODEL_ID.to_owned());
    tauri::async_runtime::spawn_blocking(move || {
        engine.install_model_with_progress(&model_id, |progress: DownloadProgress| {
            let _ = app.emit("tts-download-progress", progress);
        })?;
        Ok::<VoiceTtsStatus, String>(tts_status(&engine))
    })
    .await
    .map_err(|e| format!("Capy voice model download stopped unexpectedly: {e}"))?
}

#[tauri::command]
pub fn cancel_tts_model_download(state: State<Arc<TtsEngine>>) {
    state.cancel_download();
}

#[tauri::command]
pub async fn verify_tts_model(
    state: State<'_, Arc<TtsEngine>>,
) -> Result<VoiceTtsStatus, String> {
    let engine = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        engine.verify_model()?;
        Ok::<VoiceTtsStatus, String>(tts_status(&engine))
    })
    .await
    .map_err(|e| format!("Capy voice model verification stopped unexpectedly: {e}"))?
}

#[tauri::command]
pub fn delete_tts_model(
    state: State<Arc<TtsEngine>>,
    model_id: Option<String>,
) -> Result<VoiceTtsStatus, String> {
    if let Some(model_id) = model_id {
        state.delete_quality(&model_id)?;
    } else {
        state.delete_model()?;
    }
    Ok(tts_status(&state))
}

#[tauri::command]
pub fn set_active_tts_model(
    state: State<Arc<TtsEngine>>,
    model_id: String,
) -> Result<VoiceTtsStatus, String> {
    state.set_active_model(&model_id)?;
    Ok(tts_status(&state))
}

#[tauri::command]
pub fn cancel_tts(state: State<Arc<TtsEngine>>) {
    state.cancel_speak();
}

#[derive(Clone, Serialize)]
pub struct SpeakProgress {
    pub phase: String,
    pub message: String,
}

#[tauri::command]
pub async fn speak_tts(
    app: AppHandle,
    state: State<'_, Arc<TtsEngine>>,
    text: String,
    voice: Option<String>,
    speed: Option<f32>,
) -> Result<SpeechAudio, String> {
    let engine = state.inner().clone();
    let voice = voice.unwrap_or_else(|| sandwalk_tts::DEFAULT_VOICE.to_owned());
    let speed = speed.unwrap_or(1.0);
    tauri::async_runtime::spawn_blocking(move || {
        engine.speak_with_progress(&text, &voice, speed, |phase, message| {
            let _ = app.emit(
                "tts-speak-progress",
                SpeakProgress {
                    phase: phase.to_owned(),
                    message: message.to_owned(),
                },
            );
        })
    })
    .await
    .map_err(|e| format!("Capy speech stopped unexpectedly: {e}"))?
}
