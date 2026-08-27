//! Local Kokoro TTS: download ONNX + voice packs, then synthesize short replies.
//!
//! Hosts (Tauri) own playback. This crate stays free of UI and microphone code.

use std::{
    fs,
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Mutex,
    },
};

use kokoro_en::{KokoroTts, Voice};
use serde::Serialize;
use sha2::{Digest, Sha256};
use tokio::runtime::Runtime;

pub const DEFAULT_MODEL_FILE: &str = "model_q8f16.onnx";
pub const DEFAULT_MODEL_URL: &str =
    "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/onnx/model_q8f16.onnx";
pub const DEFAULT_MODEL_BYTES: u64 = 86_033_585;
pub const DEFAULT_MODEL_SHA256: &str =
    "04c658aec1b6008857c2ad10f8c589d4180d0ec427e7e6118ceb487e215c3cd0";
pub const DEFAULT_VOICE: &str = "af_heart";
pub const SAMPLE_RATE: u32 = 24_000;
const VOICE_URL_PREFIX: &str =
    "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main/voices/";
const MIN_VOICE_BYTES: u64 = 100_000;

#[derive(Debug, Clone, Copy, Serialize)]
pub struct VoiceInfo {
    pub id: &'static str,
    pub label: &'static str,
    pub group: &'static str,
    pub language: &'static str,
    pub language_code: &'static str,
}

/// Official v1.0 voices (English Space catalog first, then other languages).
pub const VOICES: &[VoiceInfo] = &[
    VoiceInfo { id: "af_heart", label: "Heart", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_bella", label: "Bella", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_nicole", label: "Nicole", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_aoede", label: "Aoede", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_kore", label: "Kore", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_sarah", label: "Sarah", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_nova", label: "Nova", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_sky", label: "Sky", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_alloy", label: "Alloy", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_jessica", label: "Jessica", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "af_river", label: "River", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_michael", label: "Michael", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_fenrir", label: "Fenrir", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_puck", label: "Puck", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_echo", label: "Echo", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_eric", label: "Eric", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_liam", label: "Liam", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_onyx", label: "Onyx", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_santa", label: "Santa", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "am_adam", label: "Adam", group: "English (US)", language: "English", language_code: "en" },
    VoiceInfo { id: "bf_emma", label: "Emma", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bf_isabella", label: "Isabella", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bf_alice", label: "Alice", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bf_lily", label: "Lily", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bm_george", label: "George", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bm_fable", label: "Fable", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bm_lewis", label: "Lewis", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "bm_daniel", label: "Daniel", group: "English (UK)", language: "English", language_code: "en" },
    VoiceInfo { id: "ef_dora", label: "Dora", group: "Spanish", language: "Spanish", language_code: "es" },
    VoiceInfo { id: "em_alex", label: "Alex", group: "Spanish", language: "Spanish", language_code: "es" },
    VoiceInfo { id: "em_santa", label: "Santa", group: "Spanish", language: "Spanish", language_code: "es" },
    VoiceInfo { id: "ff_siwis", label: "Siwis", group: "French", language: "French", language_code: "fr" },
    VoiceInfo { id: "hf_alpha", label: "Alpha", group: "Hindi", language: "Hindi", language_code: "hi" },
    VoiceInfo { id: "hf_beta", label: "Beta", group: "Hindi", language: "Hindi", language_code: "hi" },
    VoiceInfo { id: "hm_omega", label: "Omega", group: "Hindi", language: "Hindi", language_code: "hi" },
    VoiceInfo { id: "hm_psi", label: "Psi", group: "Hindi", language: "Hindi", language_code: "hi" },
    VoiceInfo { id: "if_sara", label: "Sara", group: "Italian", language: "Italian", language_code: "it" },
    VoiceInfo { id: "im_nicola", label: "Nicola", group: "Italian", language: "Italian", language_code: "it" },
    VoiceInfo { id: "pf_dora", label: "Dora", group: "Portuguese (Brazil)", language: "Portuguese", language_code: "pt" },
    VoiceInfo { id: "pm_alex", label: "Alex", group: "Portuguese (Brazil)", language: "Portuguese", language_code: "pt" },
    VoiceInfo { id: "pm_santa", label: "Santa", group: "Portuguese (Brazil)", language: "Portuguese", language_code: "pt" },
    VoiceInfo { id: "jf_alpha", label: "Alpha", group: "Japanese", language: "Japanese", language_code: "ja" },
    VoiceInfo { id: "jf_gongitsune", label: "Gongitsune", group: "Japanese", language: "Japanese", language_code: "ja" },
    VoiceInfo { id: "jf_nezumi", label: "Nezumi", group: "Japanese", language: "Japanese", language_code: "ja" },
    VoiceInfo { id: "jf_tebukuro", label: "Tebukuro", group: "Japanese", language: "Japanese", language_code: "ja" },
    VoiceInfo { id: "jm_kumo", label: "Kumo", group: "Japanese", language: "Japanese", language_code: "ja" },
    VoiceInfo { id: "zf_xiaobei", label: "Xiaobei", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zf_xiaoni", label: "Xiaoni", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zf_xiaoxiao", label: "Xiaoxiao", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zf_xiaoyi", label: "Xiaoyi", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zm_yunjian", label: "Yunjian", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zm_yunxi", label: "Yunxi", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zm_yunxia", label: "Yunxia", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
    VoiceInfo { id: "zm_yunyang", label: "Yunyang", group: "Mandarin", language: "Mandarin Chinese", language_code: "zh" },
];

pub fn lang_from_voice_prefix(voice_id: &str) -> &'static str {
    match voice_id.as_bytes().first().copied().unwrap_or(b'a') {
        b'a' | b'b' => "en",
        b'e' => "es",
        b'f' => "fr",
        b'h' => "hi",
        b'i' => "it",
        b'j' => "ja",
        b'p' => "pt",
        b'z' => "zh",
        _ => "en",
    }
}

pub fn voice_info(voice_id: &str) -> Option<&'static VoiceInfo> {
    VOICES.iter().find(|voice| voice.id == voice_id)
}

#[derive(Debug, Clone, Serialize)]
pub struct TtsStatus {
    pub model_installed: bool,
    pub model_verified: bool,
    pub download_in_progress: bool,
    pub model_name: &'static str,
    pub model_bytes: u64,
    pub voice_count: usize,
    pub voices_installed: usize,
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct DownloadProgress {
    pub downloaded_bytes: u64,
    pub total_bytes: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SpeechAudio {
    pub samples: Vec<f32>,
    pub sample_rate: u32,
}

pub struct TtsEngine {
    root: PathBuf,
    model_path: PathBuf,
    voices_dir: PathBuf,
    verified_marker_path: PathBuf,
    download_in_progress: AtomicBool,
    cancel_download: AtomicBool,
    cancel_speak: AtomicBool,
    runtime: Runtime,
    session: Mutex<Option<KokoroTts>>,
}

impl TtsEngine {
    pub fn new(model_dir: impl Into<PathBuf>) -> Self {
        let root = model_dir.into().join("kokoro");
        let model_path = root.join(DEFAULT_MODEL_FILE);
        let voices_dir = root.join("voices");
        let runtime = Runtime::new().expect("tokio runtime for Kokoro TTS");
        Self {
            verified_marker_path: model_path.with_extension("onnx.verified"),
            model_path,
            voices_dir,
            root,
            download_in_progress: AtomicBool::new(false),
            cancel_download: AtomicBool::new(false),
            cancel_speak: AtomicBool::new(false),
            runtime,
            session: Mutex::new(None),
        }
    }

    pub fn status(&self) -> TtsStatus {
        let voices_installed = installed_voice_count(&self.voices_dir);
        let model_installed = self.model_path.is_file();
        let model_verified = model_installed
            && model_verification_marker_matches(&self.model_path, &self.verified_marker_path)
            && voices_installed >= 1;
        TtsStatus {
            model_installed,
            model_verified,
            download_in_progress: self.download_in_progress.load(Ordering::SeqCst),
            model_name: "Kokoro 82M (local)",
            model_bytes: DEFAULT_MODEL_BYTES + estimated_voice_bytes(),
            voice_count: VOICES.len(),
            voices_installed,
        }
    }

    pub fn install_with_progress(
        &self,
        mut on_progress: impl FnMut(DownloadProgress),
    ) -> Result<(), String> {
        if self.status().model_verified {
            return Ok(());
        }
        if self
            .download_in_progress
            .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("The Capy voice model is already downloading.".to_owned());
        }
        self.cancel_download.store(false, Ordering::SeqCst);
        let result = (|| {
            fs::create_dir_all(&self.voices_dir)
                .map_err(|e| format!("Could not create the Kokoro model directory: {e}"))?;
            let total = DEFAULT_MODEL_BYTES + estimated_voice_bytes();
            let mut downloaded = 0_u64;
            download_file(
                DEFAULT_MODEL_URL,
                &self.model_path,
                DEFAULT_MODEL_BYTES,
                Some(DEFAULT_MODEL_SHA256),
                &self.cancel_download,
                |chunk| {
                    downloaded = chunk;
                    on_progress(DownloadProgress {
                        downloaded_bytes: downloaded,
                        total_bytes: total,
                    });
                },
            )?;
            write_verification_marker(&self.model_path, &self.verified_marker_path)?;
            for voice in VOICES {
                if self.cancel_download.load(Ordering::SeqCst) {
                    return Err("Capy voice model download canceled.".to_owned());
                }
                let dest = self.voices_dir.join(format!("{}.bin", voice.id));
                if dest.is_file() && fs::metadata(&dest).map(|m| m.len()).unwrap_or(0) >= MIN_VOICE_BYTES
                {
                    downloaded += 522_240;
                    on_progress(DownloadProgress {
                        downloaded_bytes: downloaded.min(total),
                        total_bytes: total,
                    });
                    continue;
                }
                let url = format!("{VOICE_URL_PREFIX}{}.bin", voice.id);
                download_file(
                    &url,
                    &dest,
                    522_240,
                    None,
                    &self.cancel_download,
                    |chunk| {
                        on_progress(DownloadProgress {
                            downloaded_bytes: (downloaded + chunk).min(total),
                            total_bytes: total,
                        });
                    },
                )?;
                downloaded += 522_240;
            }
            self.drop_session();
            on_progress(DownloadProgress {
                downloaded_bytes: total,
                total_bytes: total,
            });
            Ok(())
        })();
        self.download_in_progress.store(false, Ordering::SeqCst);
        self.cancel_download.store(false, Ordering::SeqCst);
        result
    }

    pub fn verify_model(&self) -> Result<(), String> {
        verify_model_file(&self.model_path, DEFAULT_MODEL_BYTES, DEFAULT_MODEL_SHA256)?;
        if installed_voice_count(&self.voices_dir) == 0 {
            return Err("Install at least one Kokoro voice pack.".to_owned());
        }
        write_verification_marker(&self.model_path, &self.verified_marker_path)
    }

    pub fn cancel_download(&self) {
        self.cancel_download.store(true, Ordering::SeqCst);
    }

    pub fn cancel_speak(&self) {
        self.cancel_speak.store(true, Ordering::SeqCst);
    }

    pub fn delete_model(&self) -> Result<(), String> {
        self.cancel_download();
        self.cancel_speak();
        self.drop_session();
        if self.root.exists() {
            fs::remove_dir_all(&self.root)
                .map_err(|e| format!("Could not remove the Capy voice model: {e}"))?;
        }
        Ok(())
    }

    pub fn speak(&self, text: &str, voice: &str, speed: f32) -> Result<SpeechAudio, String> {
        let text = text.trim();
        if text.is_empty() {
            return Ok(SpeechAudio {
                samples: Vec::new(),
                sample_rate: SAMPLE_RATE,
            });
        }
        if !self.status().model_verified {
            return Err("Install the Capy voice model in Settings first.".to_owned());
        }
        let voice = if voice_info(voice).is_some() {
            voice
        } else {
            DEFAULT_VOICE
        };
        let speed = speed.clamp(0.5, 2.0);
        self.cancel_speak.store(false, Ordering::SeqCst);
        let guard = self.ensure_session()?;
        let tts = guard
            .as_ref()
            .ok_or_else(|| "Capy voice engine failed to load.".to_owned())?;
        if self.cancel_speak.load(Ordering::SeqCst) {
            return Ok(SpeechAudio {
                samples: Vec::new(),
                sample_rate: SAMPLE_RATE,
            });
        }
        let samples = self
            .runtime
            .block_on(async {
                let (audio, _) = tts
                    .synth(text, Voice::new(voice).with_speed(speed))
                    .await
                    .map_err(|e| format!("Could not synthesize Capy speech: {e}"))?;
                Ok::<Vec<f32>, String>(audio)
            })?;
        Ok(SpeechAudio {
            samples,
            sample_rate: SAMPLE_RATE,
        })
    }

    fn ensure_session(&self) -> Result<std::sync::MutexGuard<'_, Option<KokoroTts>>, String> {
        let mut guard = self
            .session
            .lock()
            .map_err(|_| "Capy voice engine is busy.".to_owned())?;
        if guard.is_none() {
            let model = self.model_path.clone();
            let voices = self.voices_dir.clone();
            let tts = self.runtime.block_on(async {
                KokoroTts::new(model, voices)
                    .await
                    .map_err(|e| format!("Could not load the Capy voice model: {e}"))
            })?;
            *guard = Some(tts);
        }
        Ok(guard)
    }

    fn drop_session(&self) {
        if let Ok(mut guard) = self.session.lock() {
            *guard = None;
        }
    }
}

fn estimated_voice_bytes() -> u64 {
    VOICES.len() as u64 * 522_240
}

fn installed_voice_count(dir: &Path) -> usize {
    let Ok(entries) = fs::read_dir(dir) else {
        return 0;
    };
    entries
        .flatten()
        .filter(|entry| {
            entry
                .path()
                .extension()
                .and_then(|ext| ext.to_str())
                == Some("bin")
                && fs::metadata(entry.path()).map(|m| m.len()).unwrap_or(0) >= MIN_VOICE_BYTES
        })
        .count()
}

fn download_file(
    url: &str,
    dest: &Path,
    expected_bytes: u64,
    expected_sha: Option<&str>,
    cancel: &AtomicBool,
    mut on_progress: impl FnMut(u64),
) -> Result<(), String> {
    if dest.is_file() {
        if let Some(sha) = expected_sha {
            if verify_model_file(dest, expected_bytes, sha).is_ok() {
                on_progress(expected_bytes);
                return Ok(());
            }
        } else if fs::metadata(dest).map(|m| m.len()).unwrap_or(0) >= MIN_VOICE_BYTES {
            on_progress(expected_bytes);
            return Ok(());
        }
    }
    let parent = dest
        .parent()
        .ok_or_else(|| "Could not determine the local model directory.".to_owned())?;
    fs::create_dir_all(parent).map_err(|e| format!("Could not create model directory: {e}"))?;
    let partial = dest.with_extension("part");
    let agent = ureq::AgentBuilder::new()
        .timeout_connect(std::time::Duration::from_secs(30))
        .timeout_read(std::time::Duration::from_secs(30))
        .build();
    let response = agent
        .get(url)
        .call()
        .map_err(|e| format!("Could not download a Capy voice file: {e}"))?;
    let mut input = response.into_reader();
    let mut output =
        fs::File::create(&partial).map_err(|e| format!("Could not save a Capy voice file: {e}"))?;
    let mut downloaded = 0_u64;
    let mut last_reported = 0_u64;
    let mut buffer = [0_u8; 64 * 1024];
    on_progress(0);
    loop {
        if cancel.load(Ordering::SeqCst) {
            drop(output);
            let _ = fs::remove_file(&partial);
            return Err("Capy voice model download canceled.".to_owned());
        }
        let count = input
            .read(&mut buffer)
            .map_err(|e| format!("Could not download a Capy voice file: {e}"))?;
        if count == 0 {
            break;
        }
        output
            .write_all(&buffer[..count])
            .map_err(|e| format!("Could not save a Capy voice file: {e}"))?;
        downloaded += count as u64;
        if downloaded.saturating_sub(last_reported) >= 256 * 1024 || downloaded == expected_bytes {
            last_reported = downloaded;
            on_progress(downloaded);
        }
    }
    output
        .flush()
        .map_err(|e| format!("Could not finish saving a Capy voice file: {e}"))?;
    drop(output);
    if let Some(sha) = expected_sha {
        verify_model_file(&partial, expected_bytes, sha)?;
    } else if fs::metadata(&partial).map(|m| m.len()).unwrap_or(0) < MIN_VOICE_BYTES {
        let _ = fs::remove_file(&partial);
        return Err("A Capy voice pack downloaded incompletely.".to_owned());
    }
    if dest.exists() {
        fs::remove_file(dest).map_err(|e| format!("Could not replace a Capy voice file: {e}"))?;
    }
    fs::rename(&partial, dest).map_err(|e| format!("Could not install a Capy voice file: {e}"))?;
    Ok(())
}

fn verify_model_file(path: &Path, expected_bytes: u64, expected_sha: &str) -> Result<(), String> {
    let metadata =
        fs::metadata(path).map_err(|e| format!("Could not read the Capy voice model: {e}"))?;
    if metadata.len() != expected_bytes {
        return Err(format!(
            "The Capy voice model is incomplete ({} of {} bytes).",
            metadata.len(),
            expected_bytes
        ));
    }
    let mut file =
        fs::File::open(path).map_err(|e| format!("Could not read the Capy voice model: {e}"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 128 * 1024];
    loop {
        let count = file
            .read(&mut buffer)
            .map_err(|e| format!("Could not verify the Capy voice model: {e}"))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    let actual = format!("{:x}", hasher.finalize());
    if actual != expected_sha {
        return Err(
            "The Capy voice model failed its checksum. Repair the download in Settings.".to_owned(),
        );
    }
    Ok(())
}

fn model_modified_millis(path: &Path) -> Option<u128> {
    fs::metadata(path)
        .ok()?
        .modified()
        .ok()?
        .duration_since(std::time::UNIX_EPOCH)
        .ok()
        .map(|duration| duration.as_millis())
}

fn write_verification_marker(model_path: &Path, marker_path: &Path) -> Result<(), String> {
    let modified = model_modified_millis(model_path)
        .ok_or_else(|| "Could not read the installed Capy voice model timestamp.".to_owned())?;
    fs::write(marker_path, format!("{DEFAULT_MODEL_SHA256}\n{modified}\n"))
        .map_err(|e| format!("Could not record Capy voice model verification: {e}"))
}

fn model_verification_marker_matches(model_path: &Path, marker_path: &Path) -> bool {
    let Ok(metadata) = fs::metadata(model_path) else {
        return false;
    };
    if metadata.len() != DEFAULT_MODEL_BYTES {
        return false;
    }
    let Ok(marker) = fs::read_to_string(marker_path) else {
        return false;
    };
    let mut lines = marker.lines();
    let hash_matches = lines.next() == Some(DEFAULT_MODEL_SHA256);
    let marker_modified = lines.next().and_then(|value| value.parse::<u128>().ok());
    hash_matches && marker_modified == model_modified_millis(model_path)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lang_from_voice_prefix_maps_official_families() {
        assert_eq!(lang_from_voice_prefix("af_heart"), "en");
        assert_eq!(lang_from_voice_prefix("bm_george"), "en");
        assert_eq!(lang_from_voice_prefix("ef_dora"), "es");
        assert_eq!(lang_from_voice_prefix("ff_siwis"), "fr");
        assert_eq!(lang_from_voice_prefix("hf_alpha"), "hi");
        assert_eq!(lang_from_voice_prefix("if_sara"), "it");
        assert_eq!(lang_from_voice_prefix("jf_alpha"), "ja");
        assert_eq!(lang_from_voice_prefix("pf_dora"), "pt");
        assert_eq!(lang_from_voice_prefix("zf_xiaobei"), "zh");
    }

    #[test]
    fn default_voice_is_heart() {
        assert_eq!(VOICES[0].id, "af_heart");
        assert_eq!(voice_info("af_heart").unwrap().language_code, "en");
    }

    #[test]
    fn readiness_requires_verified_model_and_a_voice() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("sandwalk-tts-{unique}"));
        fs::create_dir_all(&dir).unwrap();
        let engine = TtsEngine::new(&dir);
        assert!(!engine.status().model_verified);
        let model = engine.model_path.clone();
        fs::create_dir_all(model.parent().unwrap()).unwrap();
        fs::File::create(&model)
            .unwrap()
            .set_len(DEFAULT_MODEL_BYTES)
            .unwrap();
        write_verification_marker(&model, &engine.verified_marker_path).unwrap();
        assert!(!engine.status().model_verified);
        fs::create_dir_all(&engine.voices_dir).unwrap();
        fs::File::create(engine.voices_dir.join("af_heart.bin"))
            .unwrap()
            .set_len(MIN_VOICE_BYTES)
            .unwrap();
        assert!(engine.status().model_verified);
        engine.delete_model().unwrap();
        assert!(!engine.status().model_installed);
        let _ = fs::remove_dir_all(dir);
    }
}
