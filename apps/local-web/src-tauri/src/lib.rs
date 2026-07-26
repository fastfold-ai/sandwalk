//! Sandwalk — Tauri client window over `apps/local-web`.
//!
//! This shell does **not** spawn `sandwalk serve`. The nested Sandwalk Server
//! helper (menubar) owns the agent. Native commands proxy to its control plane at
//! `~/Library/Application Support/Sandwalk/control.json`.

mod dictation;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
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
    inject_bootstrap_script(None)
}

fn inject_bootstrap_script(initial_route: Option<&str>) -> String {
    let os = std::env::consts::OS;
    let overlay = if os == "macos" {
        "try{document.documentElement.classList.add('sandwalk-mac-overlay');document.documentElement.dataset.platform='macos';}catch(e){}"
    } else {
        ""
    };
    let route_js = initial_route
        .filter(|r| is_spa_route(r))
        .map(|r| {
            format!(
                "window.__SANDWALK_INITIAL_ROUTE__={};",
                serde_json::to_string(r).unwrap_or_else(|_| "\"/\"".into())
            )
        })
        .unwrap_or_default();
    if let Ok(ctl) = read_control() {
        if let Some(api) = ctl.api_base {
            let trimmed = api.trim_end_matches('/').to_string();
            if !trimmed.is_empty() {
                return format!(
                    "window.__SANDWALK_HTTP__={};window.__SANDWALK_PLATFORM__='{}';{}{}",
                    serde_json::to_string(&trimmed)
                        .unwrap_or_else(|_| "\"http://127.0.0.1:8787\"".into()),
                    os,
                    route_js,
                    overlay
                );
            }
        }
    }
    format!(
        "window.__SANDWALK_HTTP__='http://127.0.0.1:8787';window.__SANDWALK_PLATFORM__='{}';{}{}",
        os, route_js, overlay
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

fn sanitize_download_filename(name: &str) -> String {
    let trimmed = name.trim();
    let base = if trimmed.is_empty() { "download" } else { trimmed };
    let safe: String = base
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || matches!(ch, '.' | '-' | '_' | ' ') {
                ch
            } else {
                '-'
            }
        })
        .collect();
    let collapsed = safe.split_whitespace().collect::<Vec<_>>().join(" ");
    if collapsed.is_empty() {
        "download".into()
    } else {
        collapsed
    }
}

fn unique_download_path(dir: &std::path::Path, filename: &str) -> PathBuf {
    let candidate = dir.join(filename);
    if !candidate.exists() {
        return candidate;
    }
    let stem = candidate
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("download");
    let ext = candidate
        .extension()
        .and_then(|s| s.to_str())
        .map(|e| format!(".{e}"))
        .unwrap_or_default();
    for index in 1..1000 {
        let next = dir.join(format!("{stem} ({index}){ext}"));
        if !next.exists() {
            return next;
        }
    }
    dir.join(format!(
        "{stem}-{}.{}{ext}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    ))
}

fn reveal_in_file_manager(path: &std::path::Path) {
    #[cfg(target_os = "macos")]
    {
        let _ = Command::new("open").args(["-R"]).arg(path).spawn();
    }
    #[cfg(target_os = "linux")]
    {
        if let Some(parent) = path.parent() {
            let _ = Command::new("xdg-open").arg(parent).spawn();
        }
    }
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("explorer")
            .args(["/select,", &path.display().to_string()])
            .spawn();
    }
}

fn write_download_file(default_filename: &str, bytes: &[u8]) -> Result<String, String> {
    let dir = dirs::download_dir()
        .or_else(dirs::home_dir)
        .ok_or_else(|| "Unable to locate Downloads folder.".to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let filename = sanitize_download_filename(default_filename);
    let path = unique_download_path(&dir, &filename);
    fs::write(&path, bytes).map_err(|e| e.to_string())?;
    reveal_in_file_manager(&path);
    Ok(path.display().to_string())
}

/// Save text to the user's Downloads folder (WebView `<a download>` is a no-op
/// in Tauri). Reveals the file in Finder on macOS.
#[tauri::command]
fn save_text_file(default_filename: String, contents: String) -> Result<String, String> {
    write_download_file(&default_filename, contents.as_bytes())
}

/// Save binary bytes (base64) to Downloads and reveal in the file manager.
#[tauri::command]
fn save_bytes_file(default_filename: String, contents_base64: String) -> Result<String, String> {
    use base64::Engine;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(contents_base64.trim())
        .map_err(|e| format!("Invalid base64 payload: {e}"))?;
    write_download_file(&default_filename, &bytes)
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

/// Write text to the system clipboard.
///
/// The webview's JS clipboard APIs are unreliable here: `navigator.clipboard`
/// needs a focused, permitted, secure context and `document.execCommand` is
/// deprecated, so both can fail silently inside WKWebView. The shell owns this
/// the same way it owns saving files.
#[tauri::command]
fn copy_to_clipboard(text: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    let candidates: Vec<Vec<&str>> = vec![vec!["pbcopy"]];
    #[cfg(target_os = "windows")]
    let candidates: Vec<Vec<&str>> = vec![vec!["clip"]];
    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    let candidates: Vec<Vec<&str>> = vec![
        vec!["wl-copy"],
        vec!["xclip", "-selection", "clipboard"],
        vec!["xsel", "--clipboard", "--input"],
    ];

    let mut last_error = String::from("no clipboard helper available");
    for parts in candidates {
        let (program, args) = parts.split_first().expect("non-empty command");
        let spawned = Command::new(program).args(args).stdin(Stdio::piped()).spawn();
        let mut child = match spawned {
            Ok(child) => child,
            Err(err) => {
                last_error = format!("{program}: {err}");
                continue;
            }
        };
        let write_result = child
            .stdin
            .as_mut()
            .ok_or_else(|| format!("{program}: no stdin"))
            .and_then(|stdin| stdin.write_all(text.as_bytes()).map_err(|e| e.to_string()));
        if let Err(err) = write_result {
            last_error = err;
            let _ = child.kill();
            continue;
        }
        match child.wait() {
            Ok(status) if status.success() => return Ok(()),
            Ok(status) => last_error = format!("{program} exited with {status}"),
            Err(err) => last_error = format!("{program}: {err}"),
        }
    }
    Err(last_error)
}

#[derive(Clone, Serialize)]
struct NavigatePayload {
    path: String,
}

/// True for in-app routes only — never absolute filesystem paths.
///
/// `std::env::args()` / single-instance argv often include the executable
/// (`/Users/.../sandwalk-desktop`). Taking the first `/…` string used to
/// navigate there and leave a blank "New Chat" shell.
fn is_spa_route(path: &str) -> bool {
    if path == "/" {
        return true;
    }
    let Some(rest) = path.strip_prefix('/') else {
        return false;
    };
    if rest.is_empty() || rest.starts_with('/') {
        return false;
    }
    let head = rest.split('/').next().unwrap_or("");
    matches!(
        head,
        "agents" | "dashboard" | "library" | "projects" | "onboarding"
    )
}

/// SPA path from env, argv (`-- /agents/<id>`), or menubar pending-route file.
fn initial_desktop_route() -> Option<String> {
    if let Ok(env_route) = std::env::var("SANDWALK_DESKTOP_ROUTE") {
        if is_spa_route(&env_route) {
            return Some(env_route);
        }
    }
    if let Some(arg) = std::env::args().skip(1).find(|arg| is_spa_route(arg)) {
        return Some(arg);
    }
    read_pending_desktop_route()
}

fn pending_desktop_route_path() -> Option<PathBuf> {
    Some(support_dir().join("pending-desktop-route"))
}

fn read_pending_desktop_route() -> Option<String> {
    let path = pending_desktop_route_path()?;
    let text = std::fs::read_to_string(&path).ok()?;
    let route = text.trim();
    if is_spa_route(route) {
        Some(route.to_string())
    } else {
        None
    }
}

fn clear_pending_desktop_route() {
    if let Some(path) = pending_desktop_route_path() {
        let _ = std::fs::remove_file(path);
    }
}

fn focus_main_window(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}

fn emit_navigate(app: &tauri::AppHandle, path: String) {
    if !is_spa_route(&path) {
        return;
    }
    let _ = app.emit("sandwalk://navigate", NavigatePayload { path });
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
        focus_main_window(app);
        // Menubar uses `open -n` so this callback runs and can revive a
        // hide-on-close window. Prefer argv SPA routes, then the pending file.
        // Skip argv[0] / absolute binary paths — they also start with `/`.
        let route = argv
            .iter()
            .skip(1)
            .find(|a| is_spa_route(a))
            .cloned()
            .or_else(read_pending_desktop_route);
        if let Some(path) = route {
            emit_navigate(app, path);
            clear_pending_desktop_route();
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
            copy_to_clipboard,
            save_text_file,
            save_bytes_file,
            dictation::get_dictation_status,
            dictation::start_dictation,
            dictation::stop_dictation,
            dictation::cancel_dictation,
            dictation::download_dictation_model,
            dictation::cancel_dictation_model_download,
            dictation::verify_dictation_model,
            dictation::mark_dictation_test_passed,
            dictation::delete_dictation_model,
            dictation::dictation_level,
        ])
        .setup(|app| {
            dictation::manage_dictation(app);
            ensure_server_helper();
            // Consume pending route once so inject + delayed emit share it.
            let cold_route = initial_desktop_route();
            let script = inject_bootstrap_script(cold_route.as_deref());
            let mut win = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Sandwalk")
                .inner_size(1280.0, 860.0)
                .min_inner_size(900.0, 600.0)
                // Tauri's native file-drop handler blocks HTML5 DnD; the composer
                // uses DOM drag/drop so OS file drops auto-upload into the session.
                .disable_drag_drop_handler()
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

            // Emit after the SPA can subscribe (setup emit is usually dropped).
            if let Some(route) = cold_route {
                let handle = app.handle().clone();
                thread::spawn(move || {
                    thread::sleep(Duration::from_millis(600));
                    focus_main_window(&handle);
                    emit_navigate(&handle, route);
                    clear_pending_desktop_route();
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Sandwalk")
        .run(|app_handle, event| {
            // Close hides the window so the Dock stays dotted. Clicking the
            // Dock icon fires Reopen — show/focus the main window again.
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen { .. } = event {
                focus_main_window(app_handle);
            }
        });
}
