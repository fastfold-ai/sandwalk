//! Apple Silicon MLX engines (Chatterbox, Qwen3) via a Python helper.

use std::{
    fs,
    io::{BufRead, BufReader, Read},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::Duration,
};

use crate::{models::MLX_MODELS, DownloadProgress, SpeechAudio, TtsModelSpec, SAMPLE_RATE};

pub fn mlx_dest(models_root: &Path, model_id: &str) -> PathBuf {
    models_root.join("mlx").join(model_id)
}

pub fn mlx_ready(models_root: &Path, spec: &TtsModelSpec) -> bool {
    mlx_dest(models_root, spec.id).join(spec.file).is_file()
}

const HELPER_SOURCE: &str = include_str!("../mlx/capy_mlx_tts.py");

fn helper_script(models_root: &Path) -> Result<PathBuf, String> {
    let dest = models_root.join("mlx").join("capy_mlx_tts.py");
    fs::create_dir_all(dest.parent().unwrap())
        .map_err(|e| format!("Could not create the MLX helper directory: {e}"))?;
    fs::write(&dest, HELPER_SOURCE)
        .map_err(|e| format!("Could not write the MLX helper: {e}"))?;
    Ok(dest)
}

fn python_minor(bin: &str) -> Option<(u8, u8)> {
    let output = Command::new(bin)
        .args([
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let mut parts = text.trim().split('.');
    Some((parts.next()?.parse().ok()?, parts.next()?.parse().ok()?))
}

fn mlx_python_ok(version: (u8, u8)) -> bool {
    version.0 == 3 && (10..=12).contains(&version.1)
}

fn find_compatible_python() -> Result<String, String> {
    let home = std::env::var("HOME").unwrap_or_default();
    let mut candidates = vec![
        "python3.12".to_owned(),
        "python3.11".to_owned(),
        "python3.10".to_owned(),
    ];
    for minor in [12u8, 11, 10] {
        candidates.push(format!("{home}/.local/bin/python3.{minor}"));
        candidates.push(format!("/opt/homebrew/bin/python3.{minor}"));
        candidates.push(format!(
            "/opt/homebrew/opt/python@{minor}/bin/python3.{minor}"
        ));
        candidates.push(format!("/usr/local/bin/python3.{minor}"));
        candidates.push(format!(
            "/usr/local/opt/python@{minor}/bin/python3.{minor}"
        ));
    }
    for candidate in candidates {
        if candidate.contains('/') && !Path::new(&candidate).is_file() {
            continue;
        }
        if python_minor(&candidate).is_some_and(mlx_python_ok) {
            return Ok(candidate);
        }
    }
    Err(
        "Chatterbox and Qwen3 need Python 3.10–3.12. Your default python3 is too new for mlx-audio. Install 3.12 with brew install python@3.12, then try Install again."
            .to_owned(),
    )
}

fn mlx_python(models_root: &Path) -> Result<PathBuf, String> {
    let venv = models_root.join("mlx").join(".venv");
    let bin = venv.join("bin").join("python");
    if bin.is_file() {
        if bin
            .to_str()
            .and_then(python_minor)
            .is_some_and(mlx_python_ok)
        {
            return Ok(bin);
        }
        let _ = fs::remove_dir_all(&venv);
    }
    let base = find_compatible_python()?;
    fs::create_dir_all(venv.parent().unwrap())
        .map_err(|e| format!("Could not create the MLX helper directory: {e}"))?;
    let status = Command::new(&base)
        .args(["-m", "venv"])
        .arg(&venv)
        .status()
        .map_err(|e| format!("Could not create the MLX Python environment: {e}"))?;
    if !status.success() || !bin.is_file() {
        return Err(
            "Could not create a Python 3.10–3.12 environment for Chatterbox and Qwen3.".to_owned(),
        );
    }
    Ok(bin)
}

pub fn install_mlx(
    models_root: &Path,
    spec: &TtsModelSpec,
    cancel: &AtomicBool,
    mut on_progress: impl FnMut(DownloadProgress),
) -> Result<(), String> {
    if !crate::models::mlx_supported() {
        return Err("Chatterbox and Qwen3 use MLX and need an Apple Silicon Mac.".to_owned());
    }
    let dest = mlx_dest(models_root, spec.id);
    fs::create_dir_all(&dest).map_err(|e| format!("Could not create the MLX model directory: {e}"))?;
    on_progress(DownloadProgress {
        downloaded_bytes: 0,
        total_bytes: spec.bytes,
        message: Some("Installing mlx-audio…".to_owned()),
    });
    let script = helper_script(models_root)?;
    let python = mlx_python(models_root)?;
    let mut child = Command::new(python)
        .arg(&script)
        .arg("install")
        .arg("--model")
        .arg(spec.id)
        .arg("--dest")
        .arg(&dest)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Could not start the MLX installer: {e}"))?;
    let reported = Arc::new(Mutex::new(DownloadProgress {
        downloaded_bytes: 0,
        total_bytes: spec.bytes,
        message: Some("Installing mlx-audio…".to_owned()),
    }));
    if let Some(pipe) = child.stdout.take() {
        let reported = reported.clone();
        let total = spec.bytes;
        thread::spawn(move || {
            for line in BufReader::new(pipe).lines().flatten() {
                if let Some(next) = parse_helper_progress(&line, total) {
                    if let Ok(mut slot) = reported.lock() {
                        *slot = next;
                    }
                }
            }
        });
    }
    let stderr_buf = Arc::new(Mutex::new(String::new()));
    if let Some(mut pipe) = child.stderr.take() {
        let stderr_buf = stderr_buf.clone();
        thread::spawn(move || {
            let mut err = String::new();
            let _ = pipe.read_to_string(&mut err);
            if let Ok(mut slot) = stderr_buf.lock() {
                *slot = err;
            }
        });
    }
    let status = loop {
        if cancel.load(Ordering::SeqCst) {
            let _ = child.kill();
            return Err("Capy voice model download canceled.".to_owned());
        }
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) => {
                let disk = dir_bytes(&dest);
                let mut progress = reported
                    .lock()
                    .map(|slot| slot.clone())
                    .unwrap_or_else(|_| DownloadProgress::bytes(0, spec.bytes));
                if disk > progress.downloaded_bytes {
                    progress.downloaded_bytes = disk.min(spec.bytes);
                    if progress.message.as_deref() == Some("Installing mlx-audio…") {
                        progress.message = Some("Downloading model files…".to_owned());
                    }
                }
                on_progress(progress);
                thread::sleep(Duration::from_millis(250));
            }
            Err(e) => return Err(format!("MLX installer stopped: {e}")),
        }
    };
    if !status.success() {
        let err = stderr_buf
            .lock()
            .map(|slot| slot.clone())
            .unwrap_or_default();
        return Err(format!(
            "Could not install {}: {}",
            spec.name,
            err.trim().lines().last().unwrap_or("mlx-audio install failed")
        ));
    }
    if !mlx_ready(models_root, spec) {
        return Err(format!("{} downloaded incompletely.", spec.name));
    }
    on_progress(DownloadProgress {
        downloaded_bytes: spec.bytes,
        total_bytes: spec.bytes,
        message: Some("Installed".to_owned()),
    });
    Ok(())
}

fn dir_bytes(path: &Path) -> u64 {
    let Ok(entries) = fs::read_dir(path) else {
        return 0;
    };
    entries
        .flatten()
        .map(|entry| {
            let child = entry.path();
            if child.is_dir() {
                dir_bytes(&child)
            } else {
                entry.metadata().map(|meta| meta.len()).unwrap_or(0)
            }
        })
        .sum()
}

fn parse_helper_progress(line: &str, fallback_total: u64) -> Option<DownloadProgress> {
    if !line.starts_with('{') {
        return None;
    }
    let downloaded = json_u64(line, "downloaded").unwrap_or(0);
    let total = json_u64(line, "total").filter(|value| *value > 0).unwrap_or(fallback_total);
    let message = json_string(line, "message").or_else(|| {
        match json_string(line, "phase")?.as_str() {
            "deps" => Some("Installing mlx-audio…".to_owned()),
            "download" => Some("Downloading model files…".to_owned()),
            "ready" => Some("Installed".to_owned()),
            _ => None,
        }
    });
    Some(DownloadProgress {
        downloaded_bytes: downloaded.min(total),
        total_bytes: total,
        message,
    })
}

fn json_u64(line: &str, key: &str) -> Option<u64> {
    let rest = line.split(&format!("\"{key}\"")).nth(1)?;
    rest.trim_start_matches([' ', ':'])
        .split([',', '}'])
        .next()?
        .trim()
        .parse()
        .ok()
}

fn json_string(line: &str, key: &str) -> Option<String> {
    let rest = line.split(&format!("\"{key}\"")).nth(1)?;
    let rest = rest.trim_start_matches([' ', ':']);
    if !rest.starts_with('"') {
        return None;
    }
    rest.get(1..)?.split('"').next().map(str::to_owned)
}

pub fn delete_mlx(models_root: &Path, spec: &TtsModelSpec) -> Result<(), String> {
    let dest = mlx_dest(models_root, spec.id);
    if dest.exists() {
        fs::remove_dir_all(&dest)
            .map_err(|e| format!("Could not remove {}: {e}", spec.name))?;
    }
    Ok(())
}

pub fn speak_mlx(
    models_root: &Path,
    spec: &TtsModelSpec,
    text: &str,
    voice: &str,
    language: &str,
    cancel: &AtomicBool,
    mut on_phase: impl FnMut(&str, &str),
) -> Result<SpeechAudio, String> {
    if cancel.load(Ordering::SeqCst) {
        return Ok(SpeechAudio {
            samples: Vec::new(),
            sample_rate: SAMPLE_RATE,
        });
    }
    if !mlx_ready(models_root, spec) {
        return Err(format!("Install {} in Settings first.", spec.name));
    }
    let dest = mlx_dest(models_root, spec.id);
    let out = dest.join("last.wav");
    let script = helper_script(models_root)?;
    let python = mlx_python(models_root)?;
    let mut child = Command::new(python)
        .arg(&script)
        .arg("speak")
        .arg("--model")
        .arg(spec.id)
        .arg("--dest")
        .arg(&dest)
        .arg("--text")
        .arg(text)
        .arg("--voice")
        .arg(voice)
        .arg("--lang")
        .arg(language)
        .arg("--out")
        .arg(&out)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Could not start MLX speech: {e}"))?;
    on_phase("loading", "Loading model into memory…");
    let stderr_buf = Arc::new(Mutex::new(String::new()));
    if let Some(mut pipe) = child.stderr.take() {
        let stderr_buf = stderr_buf.clone();
        thread::spawn(move || {
            let mut err = String::new();
            let _ = pipe.read_to_string(&mut err);
            if let Ok(mut slot) = stderr_buf.lock() {
                *slot = err;
            }
        });
    }
    if let Some(pipe) = child.stdout.take() {
        for line in BufReader::new(pipe).lines().flatten() {
            if cancel.load(Ordering::SeqCst) {
                let _ = child.kill();
                return Ok(SpeechAudio {
                    samples: Vec::new(),
                    sample_rate: SAMPLE_RATE,
                });
            }
            if let Some(progress) = parse_helper_progress(&line, spec.bytes) {
                if let Some(message) = progress.message.as_deref() {
                    let phase = json_string(&line, "phase").unwrap_or_else(|| "loading".to_owned());
                    on_phase(&phase, message);
                }
            }
        }
    }
    let status = child
        .wait()
        .map_err(|e| format!("MLX speech stopped: {e}"))?;
    if !status.success() {
        let err = stderr_buf
            .lock()
            .map(|slot| slot.clone())
            .unwrap_or_default();
        return Err(format!(
            "Could not speak with {}: {}",
            spec.name,
            err.trim().lines().last().unwrap_or("mlx-audio failed")
        ));
    }
    read_wav(&out)
}

fn read_wav(path: &Path) -> Result<SpeechAudio, String> {
    let bytes =
        fs::read(path).map_err(|e| format!("Could not read MLX speech audio: {e}"))?;
    if bytes.len() < 44 || &bytes[0..4] != b"RIFF" || &bytes[8..12] != b"WAVE" {
        return Err("MLX speech audio was not a WAV file.".to_owned());
    }
    let channels = u16::from_le_bytes([bytes[22], bytes[23]]) as usize;
    let sample_rate = u32::from_le_bytes([bytes[24], bytes[25], bytes[26], bytes[27]]);
    let bits = u16::from_le_bytes([bytes[34], bytes[35]]);
    let data_offset = bytes
        .windows(4)
        .position(|window| window == b"data")
        .map(|index| index + 8)
        .ok_or_else(|| "MLX speech audio is missing a data chunk.".to_owned())?;
    let pcm = &bytes[data_offset..];
    let samples = if bits == 16 {
        pcm.chunks_exact(2)
            .step_by(channels.max(1))
            .map(|pair| i16::from_le_bytes([pair[0], pair[1]]) as f32 / 32768.0)
            .collect()
    } else if bits == 32 {
        pcm.chunks_exact(4)
            .step_by(channels.max(1))
            .map(|pair| f32::from_le_bytes([pair[0], pair[1], pair[2], pair[3]]))
            .collect()
    } else {
        return Err(format!("Unsupported MLX wav bit depth: {bits}"));
    };
    Ok(SpeechAudio {
        samples,
        sample_rate: if sample_rate == 0 {
            SAMPLE_RATE
        } else {
            sample_rate
        },
    })
}

#[allow(dead_code)]
pub fn mlx_specs() -> &'static [TtsModelSpec] {
    MLX_MODELS
}
