//! Sandwalk — Tauri client window over `apps/local-web`.
//!
//! This shell does **not** spawn `sandwalk serve`. The nested Sandwalk Server
//! helper (menubar) owns the agent. Native commands proxy to its control plane at
//! `~/Library/Application Support/Sandwalk/control.json`.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::thread;
use std::time::Duration;
use tauri::{Emitter, Manager, WebviewUrl, WebviewWindowBuilder};

#[derive(Debug, Clone, Deserialize)]
struct ControlFile {
    host: String,
    port: u16,
    token: String,
    #[serde(default)]
    api_base: Option<String>,
    #[serde(default)]
    #[allow(dead_code)]
    dashboard_url: Option<String>,
}

fn support_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Library/Application Support/Sandwalk")
}

fn control_path() -> PathBuf {
    support_dir().join("control.json")
}

fn read_control() -> Result<ControlFile, String> {
    let path = control_path();
    let raw = fs::read_to_string(&path).map_err(|_| {
        format!(
            "Sandwalk Server control plane not found at {}. Is Sandwalk Server running?",
            path.display()
        )
    })?;
    serde_json::from_str(&raw).map_err(|e| format!("Invalid control.json: {e}"))
}

fn control_request(method: &str, path: &str, body: Option<Value>) -> Result<Value, String> {
    let ctl = read_control()?;
    let url = format!("http://{}:{}{}", ctl.host, ctl.port, path);
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .map_err(|e| e.to_string())?;
    let mut req = match method {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "PUT" => client.put(&url),
        "PATCH" => client.patch(&url),
        _ => return Err(format!("unsupported method {method}")),
    };
    req = req.header("Authorization", format!("Bearer {}", ctl.token));
    if let Some(b) = body {
        req = req.json(&b);
    }
    let res = req.send().map_err(|e| e.to_string())?;
    let status = res.status();
    let text = res.text().map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("control plane {status}: {text}"));
    }
    if text.trim().is_empty() {
        return Ok(Value::Null);
    }
    serde_json::from_str(&text).map_err(|e| format!("bad JSON: {e} — {text}"))
}

fn inject_api_base() -> String {
    let os = std::env::consts::OS;
    let overlay = if os == "macos" {
        "try{document.documentElement.classList.add('sandwalk-mac-overlay');document.documentElement.dataset.platform='macos';}catch(e){}"
    } else {
        ""
    };
    if let Ok(ctl) = read_control() {
        if let Some(api) = ctl.api_base {
            let trimmed = api.trim_end_matches('/').to_string();
            if !trimmed.is_empty() {
                return format!(
                    "window.__SANDWALK_HTTP__={};window.__SANDWALK_PLATFORM__='{}';{}",
                    serde_json::to_string(&trimmed).unwrap_or_else(|_| "\"http://127.0.0.1:8787\"".into()),
                    os,
                    overlay
                );
            }
        }
    }
    format!(
        "window.__SANDWALK_HTTP__='http://127.0.0.1:8787';window.__SANDWALK_PLATFORM__='{}';{}",
        os,
        overlay
    )
}

#[tauri::command]
fn desktop_server_status() -> Result<Value, String> {
    control_request("GET", "/v1/control/status", None)
}

#[tauri::command]
fn desktop_server_start() -> Result<Value, String> {
    control_request("POST", "/v1/control/start", None)
}

#[tauri::command]
fn desktop_server_stop() -> Result<Value, String> {
    control_request("POST", "/v1/control/stop", None)
}

#[tauri::command]
fn desktop_server_restart() -> Result<Value, String> {
    control_request("POST", "/v1/control/restart", None)
}

#[tauri::command]
fn desktop_get_settings() -> Result<Value, String> {
    control_request("GET", "/v1/control/settings", None)
}

#[tauri::command]
fn desktop_put_settings(settings: Value) -> Result<Value, String> {
    control_request("PUT", "/v1/control/settings", Some(settings))
}

#[tauri::command]
fn desktop_get_auth() -> Result<Value, String> {
    control_request("GET", "/v1/control/auth", None)
}

#[tauri::command]
fn desktop_put_auth(auth: Value) -> Result<Value, String> {
    control_request("PUT", "/v1/control/auth", Some(auth))
}

#[tauri::command]
fn desktop_get_desktop() -> Result<Value, String> {
    control_request("GET", "/v1/control/desktop", None)
}

#[tauri::command]
fn desktop_put_desktop(prefs: Value) -> Result<Value, String> {
    control_request("PUT", "/v1/control/desktop", Some(prefs))
}

#[tauri::command]
fn desktop_tail_logs(name: Option<String>, lines: Option<u32>) -> Result<Value, String> {
    let file = name.unwrap_or_else(|| "server.log".into());
    let n = lines.unwrap_or(200);
    let path = format!("/v1/control/logs?name={file}&lines={n}");
    control_request("GET", &path, None)
}

#[tauri::command]
fn desktop_rebuild_dashboard() -> Result<Value, String> {
    control_request("POST", "/v1/control/rebuild-dashboard", None)
}

#[tauri::command]
fn desktop_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
fn desktop_menubar_available() -> bool {
    read_control().is_ok()
}

#[tauri::command]
fn start_window_drag(window: tauri::WebviewWindow) -> bool {
    window.start_dragging().is_ok()
}

/// Double-click title bar — same as native macOS zoom/maximize toggle.
#[tauri::command]
fn toggle_maximize(window: tauri::WebviewWindow) -> Result<bool, String> {
    let maximized = window.is_maximized().map_err(|e| e.to_string())?;
    if maximized {
        window.unmaximize().map_err(|e| e.to_string())?;
        Ok(false)
    } else {
        window.maximize().map_err(|e| e.to_string())?;
        Ok(true)
    }
}

/// Open a URL in the system browser (Safari / default handler).
#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return Err("url is required".into());
    }
    #[cfg(target_os = "macos")]
    {
        Command::new("open")
            .arg(trimmed)
            .spawn()
            .map_err(|e| e.to_string())?;
        return Ok(());
    }
    #[cfg(not(target_os = "macos"))]
    {
        Command::new("xdg-open")
            .arg(trimmed)
            .spawn()
            .map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[derive(Clone, Serialize)]
struct NavigatePayload {
    path: String,
}

/// True when the menubar control plane answers (file alone can be stale).
fn control_plane_alive() -> bool {
    let Ok(ctl) = read_control() else {
        return false;
    };
    let url = format!("http://{}:{}/v1/control/status", ctl.host, ctl.port);
    let Ok(client) = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(1))
        .build()
    else {
        return false;
    };
    let Ok(res) = client
        .get(&url)
        .header("Authorization", format!("Bearer {}", ctl.token))
        .send()
    else {
        return false;
    };
    res.status().is_success()
}

/// Nested helper path: `Sandwalk.app/Contents/Helpers/Sandwalk Server.app`.
#[cfg(target_os = "macos")]
fn nested_server_helper_app() -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let contents = exe.parent()?.parent()?;
    let app = contents.join("Helpers").join("Sandwalk Server.app");
    if app.is_dir() {
        Some(app)
    } else {
        None
    }
}

/// Launch nested Sandwalk Server via `open` so the menubar status item registers.
#[cfg(target_os = "macos")]
fn ensure_server_helper() {
    if control_plane_alive() {
        let _ = control_request("POST", "/v1/control/start", None);
        return;
    }
    let Some(helper_app) = nested_server_helper_app() else {
        return;
    };
    // `-g` = don't steal focus; `-a` requires a proper .app bundle (not the raw binary).
    let _ = Command::new("open")
        .args(["-ga"])
        .arg(&helper_app)
        .status();
    for _ in 0..100 {
        if control_plane_alive() {
            let _ = control_request("POST", "/v1/control/start", None);
            return;
        }
        thread::sleep(Duration::from_millis(100));
    }
}

#[cfg(not(target_os = "macos"))]
fn ensure_server_helper() {}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();
    builder = builder.plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
        if let Some(win) = app.get_webview_window("main") {
            let _ = win.unminimize();
            let _ = win.show();
            let _ = win.set_focus();
        }
        // argv may include a route like `/dashboard/status`
        if let Some(route) = argv.iter().find(|a| a.starts_with('/')) {
            let _ = app.emit("sandwalk://navigate", NavigatePayload { path: route.clone() });
        }
        if let Ok(env_route) = std::env::var("SANDWALK_DESKTOP_ROUTE") {
            if env_route.starts_with('/') {
                let _ = app.emit(
                    "sandwalk://navigate",
                    NavigatePayload {
                        path: env_route,
                    },
                );
            }
        }
    }));

    builder
        .invoke_handler(tauri::generate_handler![
            desktop_server_status,
            desktop_server_start,
            desktop_server_stop,
            desktop_server_restart,
            desktop_get_settings,
            desktop_put_settings,
            desktop_get_auth,
            desktop_put_auth,
            desktop_get_desktop,
            desktop_put_desktop,
            desktop_tail_logs,
            desktop_rebuild_dashboard,
            desktop_app_version,
            desktop_menubar_available,
            start_window_drag,
            toggle_maximize,
            open_external_url,
        ])
        .setup(|app| {
            ensure_server_helper();
            let script = inject_api_base();
            let mut win = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Sandwalk")
                .inner_size(1280.0, 860.0)
                .min_inner_size(900.0, 600.0)
                .initialization_script(&script);

            #[cfg(target_os = "macos")]
            {
                // Overlay title bar: traffic lights float over the UI. Position matches
                // OpenWorker so the sidebar chrome can pad left/top to clear them.
                win = win
                    .title_bar_style(tauri::TitleBarStyle::Overlay)
                    .hidden_title(true)
                    .traffic_light_position(tauri::LogicalPosition::new(19.0, 24.0));
            }

            let window = win.build()?;

            // Close hides the window; menubar keeps the agent running.
            let win_clone = window.clone();
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                    api.prevent_close();
                    let _ = win_clone.hide();
                }
            });

            if let Ok(route) = std::env::var("SANDWALK_DESKTOP_ROUTE") {
                if route.starts_with('/') {
                    let _ = app.emit(
                        "sandwalk://navigate",
                        NavigatePayload { path: route },
                    );
                }
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Sandwalk");
}
