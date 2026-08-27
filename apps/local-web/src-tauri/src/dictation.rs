//! Local Whisper dictation — Tauri commands over the `sandwalk-stt` crate.

use sandwalk_stt::{Dictation, DownloadProgress, SttModelStatus};
use serde::Serialize;
use std::process::Command;
use std::sync::Arc;
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Clone, Serialize)]
pub struct VoiceInputStatus {
    pub recording: bool,
    pub model_installed: bool,
    pub model_verified: bool,
    pub test_passed: bool,
    pub download_in_progress: bool,
    pub model_name: &'static str,
    pub model_bytes: u64,
    pub active_model: String,
    pub models: Vec<SttModelStatus>,
    pub supported: bool,
    pub device_summary: String,
    pub compatibility_reason: Option<String>,
}

fn voice_input_status(dictation: &Dictation) -> VoiceInputStatus {
    let status = dictation.status();
    let (supported, device_summary, compatibility_reason) = voice_input_compatibility();
    VoiceInputStatus {
        recording: status.recording,
        model_installed: status.model_installed,
        model_verified: status.model_verified,
        test_passed: status.test_passed,
        download_in_progress: status.download_in_progress,
        model_name: status.model_name,
        model_bytes: status.model_bytes,
        active_model: status.active_model,
        models: status.models,
        supported,
        device_summary,
        compatibility_reason,
    }
}

#[cfg(target_os = "macos")]
fn voice_input_compatibility() -> (bool, String, Option<String>) {
    let version = Command::new("/usr/bin/sw_vers")
        .arg("-productVersion")
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_owned())
        .unwrap_or_else(|| "unknown version".to_owned());
    let major = version
        .split('.')
        .next()
        .and_then(|part| part.parse::<u32>().ok())
        .unwrap_or(0);
    let apple_silicon = std::env::consts::ARCH == "aarch64";
    let supported = apple_silicon && major >= 12;
    let architecture = if apple_silicon {
        "Apple Silicon"
    } else {
        "Intel"
    };
    let summary = format!("macOS {version} · {architecture}");
    let reason = if !apple_silicon {
        Some("Voice Input currently requires an Apple Silicon Mac (M1 or newer).".to_owned())
    } else if major < 12 {
        Some("Voice Input requires macOS 12 or newer.".to_owned())
    } else {
        None
    };
    (supported, summary, reason)
}

#[cfg(target_os = "windows")]
fn voice_input_compatibility() -> (bool, String, Option<String>) {
    let version = Command::new("cmd")
        .args(["/C", "ver"])
        .output()
        .ok()
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_owned())
        .unwrap_or_else(|| "Windows (unknown version)".to_owned());
    let build = version
        .split(|character: char| !character.is_ascii_digit() && character != '.')
        .find(|part| part.matches('.').count() >= 2)
        .and_then(|part| part.split('.').nth(2))
        .and_then(|part| part.parse::<u32>().ok())
        .unwrap_or(0);
    let x64 = std::env::consts::ARCH == "x86_64";
    let supported = x64 && build >= 19_045;
    let reason = if !x64 {
        Some("Voice Input currently requires a 64-bit x64 Windows PC.".to_owned())
    } else if build < 19_045 {
        Some("Voice Input requires Windows 10 22H2 or Windows 11.".to_owned())
    } else {
        None
    };
    (supported, format!("{version} · x64"), reason)
}

#[cfg(not(any(target_os = "macos", target_os = "windows")))]
fn voice_input_compatibility() -> (bool, String, Option<String>) {
    (
        false,
        format!("{} · {}", std::env::consts::OS, std::env::consts::ARCH),
        Some("Voice Input is currently supported on macOS and Windows.".to_owned()),
    )
}

/// App-data `models/` directory for Whisper weights + readiness markers.
pub fn models_dir() -> std::path::PathBuf {
    #[cfg(target_os = "macos")]
    {
        return dirs::home_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."))
            .join("Library/Application Support/Sandwalk/models");
    }
    #[cfg(target_os = "windows")]
    {
        return dirs::data_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."))
            .join("Sandwalk")
            .join("models");
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows")))]
    {
        return dirs::config_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."))
            .join("sandwalk")
            .join("models");
    }
}

pub fn manage_dictation(app: &mut tauri::App) {
    let _ = std::fs::create_dir_all(models_dir());
    app.manage(Arc::new(Dictation::new(models_dir())));
}

#[tauri::command]
pub fn get_dictation_status(state: State<Arc<Dictation>>) -> VoiceInputStatus {
    voice_input_status(&state)
}

#[tauri::command]
pub async fn start_dictation(
    state: State<'_, Arc<Dictation>>,
) -> Result<VoiceInputStatus, String> {
    let (supported, _, reason) = voice_input_compatibility();
    if !supported {
        return Err(
            reason.unwrap_or_else(|| "Voice Input is not supported on this device.".to_owned())
        );
    }
    let dictation = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        dictation.start()?;
        Ok::<VoiceInputStatus, String>(voice_input_status(&dictation))
    })
    .await
    .map_err(|e| format!("Dictation failed to start: {e}"))?
}

#[tauri::command]
pub async fn stop_dictation(state: State<'_, Arc<Dictation>>) -> Result<String, String> {
    let dictation = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || dictation.stop_and_transcribe())
        .await
        .map_err(|e| format!("Dictation stopped unexpectedly: {e}"))?
}

#[tauri::command]
pub fn cancel_dictation(state: State<Arc<Dictation>>) {
    state.cancel();
}

#[tauri::command]
pub async fn download_dictation_model(
    app: AppHandle,
    state: State<'_, Arc<Dictation>>,
    model_id: Option<String>,
) -> Result<VoiceInputStatus, String> {
    let dictation = state.inner().clone();
    let model_id = model_id.unwrap_or_else(|| "en".to_owned());
    tauri::async_runtime::spawn_blocking(move || {
        dictation.install_model_with_progress(&model_id, |progress: DownloadProgress| {
            let _ = app.emit("dictation-download-progress", progress);
        })?;
        Ok::<VoiceInputStatus, String>(voice_input_status(&dictation))
    })
    .await
    .map_err(|e| format!("Voice model download stopped unexpectedly: {e}"))?
}

#[tauri::command]
pub fn cancel_dictation_model_download(state: State<Arc<Dictation>>) {
    state.cancel_model_download();
}

#[tauri::command]
pub async fn verify_dictation_model(
    state: State<'_, Arc<Dictation>>,
    model_id: Option<String>,
) -> Result<VoiceInputStatus, String> {
    let dictation = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        if let Some(model_id) = model_id {
            dictation.verify_model(&model_id)?;
        } else {
            dictation.verify_default_model()?;
        }
        Ok::<VoiceInputStatus, String>(voice_input_status(&dictation))
    })
    .await
    .map_err(|e| format!("Voice model verification stopped unexpectedly: {e}"))?
}

#[tauri::command]
pub fn mark_dictation_test_passed(
    state: State<Arc<Dictation>>,
) -> Result<VoiceInputStatus, String> {
    state.mark_test_passed()?;
    Ok(voice_input_status(&state))
}

#[tauri::command]
pub fn delete_dictation_model(
    state: State<Arc<Dictation>>,
    model_id: Option<String>,
) -> Result<VoiceInputStatus, String> {
    if let Some(model_id) = model_id {
        state.delete_model(&model_id)?;
    } else {
        state.delete_default_model()?;
    }
    Ok(voice_input_status(&state))
}

#[tauri::command]
pub fn set_active_dictation_model(
    state: State<Arc<Dictation>>,
    model_id: String,
) -> Result<VoiceInputStatus, String> {
    state.set_active_model(&model_id)?;
    Ok(voice_input_status(&state))
}

#[tauri::command]
pub fn dictation_level(state: State<Arc<Dictation>>) -> f32 {
    state.input_level()
}
