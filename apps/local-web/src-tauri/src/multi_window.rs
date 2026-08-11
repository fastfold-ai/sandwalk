//! Multi-window File menu, Open Recent, and per-window backend bootstrap.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::menu::{MenuBuilder, MenuEvent, PredefinedMenuItem, SubmenuBuilder};
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder};

const MAX_RECENTS: usize = 12;
pub const DEFAULT_API: &str = "http://127.0.0.1:8787";

#[derive(Debug, Clone)]
struct WindowMeta {
    url: String,
    snapshot_id: String,
}

fn window_metas() -> &'static Mutex<HashMap<String, WindowMeta>> {
    static MAP: OnceLock<Mutex<HashMap<String, WindowMeta>>> = OnceLock::new();
    MAP.get_or_init(|| Mutex::new(HashMap::new()))
}

fn new_snapshot_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    static SEQ: AtomicU64 = AtomicU64::new(1);
    format!(
        "snap-{}-{}",
        now_secs(),
        SEQ.fetch_add(1, Ordering::Relaxed)
    )
}

/// Snapshot of a window so Open Recent can reopen it “as it was”.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WindowRecent {
    /// Stable id for this window snapshot (survives reopen).
    #[serde(default)]
    pub id: String,
    pub url: String,
    /// Last SPA route (e.g. `/agents/abc` or `/dashboard/bench`).
    #[serde(default)]
    pub route: String,
    /// Last Dock / menu title (chat or page name).
    #[serde(default)]
    pub title: String,
    /// Legacy field — kept for older window-recents.json files.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    pub last_opened_at: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OpenWindowArgs {
    pub backend_url: Option<String>,
    pub api_key: Option<String>,
    pub title: Option<String>,
    pub route: Option<String>,
    pub snapshot_id: Option<String>,
    /// When true, focus an existing window for this snapshot/url instead of opening another.
    #[serde(default)]
    pub focus_existing: bool,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct MenuActionPayload {
    action: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    url: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    route: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    snapshot_id: Option<String>,
}

fn support_dir() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("Library")
        .join("Application Support")
        .join("Sandwalk")
}

fn recents_path() -> PathBuf {
    support_dir().join("window-recents.json")
}

fn now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub fn normalize_url(url: &str) -> String {
    let trimmed = url.trim().trim_end_matches('/').to_string();
    if trimmed.is_empty() {
        DEFAULT_API.into()
    } else {
        trimmed
    }
}

pub fn read_recents() -> Vec<WindowRecent> {
    let path = recents_path();
    let Ok(raw) = fs::read_to_string(&path) else {
        return Vec::new();
    };
    let mut rows = serde_json::from_str::<Vec<WindowRecent>>(&raw).unwrap_or_default();
    // Migrate legacy URL-only rows (no snapshot id).
    let mut dirty = false;
    for row in &mut rows {
        if row.id.trim().is_empty() {
            row.id = new_snapshot_id();
            dirty = true;
        }
        if row.route.trim().is_empty() {
            row.route = "/".into();
            dirty = true;
        }
        if row.title.trim().is_empty() {
            row.title = display_title(row);
            dirty = true;
        }
    }
    if dirty {
        let _ = write_recents(&rows);
    }
    rows
}

fn write_recents(rows: &[WindowRecent]) -> Result<(), String> {
    let dir = support_dir();
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let raw = serde_json::to_string_pretty(rows).map_err(|e| e.to_string())?;
    fs::write(recents_path(), raw).map_err(|e| e.to_string())
}

fn display_title(row: &WindowRecent) -> String {
    let title = row.title.trim();
    if !title.is_empty() {
        return title.to_string();
    }
    if let Some(label) = row.label.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        return label.to_string();
    }
    window_title_for_url(&row.url)
}

fn recent_menu_label(row: &WindowRecent) -> String {
    let title = display_title(row);
    let url = normalize_url(&row.url);
    if url.contains("127.0.0.1") || url.to_lowercase().contains("localhost") {
        return title;
    }
    let host = window_title_for_url(&url)
        .strip_prefix("Sandwalk — ")
        .unwrap_or(&url)
        .to_string();
    format!("{title} — {host}")
}

/// Upsert a window snapshot into Open Recent (keyed by snapshot id).
pub fn upsert_recent_snapshot(
    snapshot_id: &str,
    url: &str,
    route: &str,
    title: &str,
) {
    let url = normalize_url(url);
    let route = {
        let t = route.trim();
        if t.is_empty() { "/" } else { t }
    }
    .to_string();
    let title = {
        let t = title.trim();
        if t.is_empty() {
            window_title_for_url(&url)
        } else {
            t.to_string()
        }
    };
    let id = if snapshot_id.trim().is_empty() {
        new_snapshot_id()
    } else {
        snapshot_id.trim().to_string()
    };
    let mut rows = read_recents();
    rows.retain(|r| r.id != id && !(r.id.is_empty() && normalize_url(&r.url) == url && r.route == route));
    rows.insert(
        0,
        WindowRecent {
            id,
            url,
            route,
            title,
            label: None,
            last_opened_at: now_secs(),
        },
    );
    rows.truncate(MAX_RECENTS);
    let _ = write_recents(&rows);
}

/// Legacy helper — records a bare server entry (no route/title yet).
pub fn remember_recent(url: &str) {
    upsert_recent_snapshot(&new_snapshot_id(), url, "/", &window_title_for_url(url));
}

pub fn clear_recents() {
    let _ = write_recents(&[]);
}

pub fn window_title_for_url(url: &str) -> String {
    let url = normalize_url(url);
    if url.contains("127.0.0.1") || url.to_lowercase().contains("localhost") {
        return "Sandwalk".into();
    }
    // Strip scheme for a short Dock / menu title: host:port
    let rest = url
        .strip_prefix("https://")
        .or_else(|| url.strip_prefix("http://"))
        .unwrap_or(&url);
    let hostport = rest.split('/').next().unwrap_or(rest);
    if hostport.is_empty() {
        format!("Sandwalk — {url}")
    } else {
        format!("Sandwalk — {hostport}")
    }
}

pub fn focused_backend_url(app: &AppHandle, fallback: &str) -> String {
    if let Some((label, _)) = app
        .webview_windows()
        .into_iter()
        .find(|(_, w)| w.is_focused().unwrap_or(false))
    {
        if let Ok(map) = window_metas().lock() {
            if let Some(meta) = map.get(label.as_str()) {
                return meta.url.clone();
            }
        }
    }
    if let Ok(map) = window_metas().lock() {
        if let Some(meta) = map.get("main") {
            return meta.url.clone();
        }
    }
    normalize_url(fallback)
}

pub fn find_window_for_snapshot(app: &AppHandle, snapshot_id: &str) -> Option<WebviewWindow> {
    if snapshot_id.is_empty() {
        return None;
    }
    let map = window_metas().lock().ok()?;
    for (label, meta) in map.iter() {
        if meta.snapshot_id == snapshot_id {
            if let Some(win) = app.get_webview_window(label) {
                return Some(win);
            }
        }
    }
    None
}

pub fn find_window_for_url(app: &AppHandle, url: &str) -> Option<WebviewWindow> {
    let want = normalize_url(url);
    let map = window_metas().lock().ok()?;
    for (label, meta) in map.iter() {
        if normalize_url(&meta.url) == want {
            if let Some(win) = app.get_webview_window(label) {
                return Some(win);
            }
        }
    }
    None
}

pub fn register_window_backend(label: &str, url: &str) -> String {
    let url = normalize_url(url);
    let snapshot_id = {
        let mut map = window_metas().lock().unwrap_or_else(|e| e.into_inner());
        if let Some(existing) = map.get(label) {
            let id = existing.snapshot_id.clone();
            map.insert(
                label.to_string(),
                WindowMeta {
                    url: url.clone(),
                    snapshot_id: id.clone(),
                },
            );
            id
        } else {
            let id = new_snapshot_id();
            map.insert(
                label.to_string(),
                WindowMeta {
                    url: url.clone(),
                    snapshot_id: id.clone(),
                },
            );
            id
        }
    };
    snapshot_id
}

pub fn register_window_backend_with_snapshot(
    label: &str,
    url: &str,
    snapshot_id: Option<&str>,
) -> String {
    let url = normalize_url(url);
    let id = snapshot_id
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .unwrap_or_else(new_snapshot_id);
    if let Ok(mut map) = window_metas().lock() {
        map.insert(
            label.to_string(),
            WindowMeta {
                url,
                snapshot_id: id.clone(),
            },
        );
    }
    id
}

pub fn unregister_window_backend(label: &str) {
    if let Ok(mut map) = window_metas().lock() {
        map.remove(label);
    }
}

pub fn snapshot_id_for_label(label: &str) -> Option<String> {
    window_metas()
        .lock()
        .ok()
        .and_then(|map| map.get(label).map(|m| m.snapshot_id.clone()))
}

pub fn inject_bootstrap_script(
    initial_route: Option<&str>,
    backend_url: &str,
    api_key: Option<&str>,
    snapshot_id: Option<&str>,
    window_kind: &str,
    is_spa_route: impl Fn(&str) -> bool,
) -> String {
    let os = std::env::consts::OS;
    let overlay = if os == "macos" {
        "try{document.documentElement.classList.add('sandwalk-mac-overlay','sandwalk-mac-glass');document.documentElement.dataset.platform='macos';}catch(e){}"
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
    let snap_js = snapshot_id
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| {
            format!(
                "window.__SANDWALK_SNAPSHOT_ID__={};",
                serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into())
            )
        })
        .unwrap_or_default();
    let http = serde_json::to_string(&normalize_url(backend_url))
        .unwrap_or_else(|_| format!("\"{DEFAULT_API}\""));
    let kind = serde_json::to_string(window_kind).unwrap_or_else(|_| "\"client\"".into());
    let key_js = api_key
        .map(str::trim)
        .filter(|k| !k.is_empty())
        .map(|k| {
            format!(
                "window.__SANDWALK_API_KEY__={};",
                serde_json::to_string(k).unwrap_or_else(|_| "\"\"".into())
            )
        })
        .unwrap_or_default();
    format!(
        "window.__SANDWALK_HTTP__={http};window.__SANDWALK_PLATFORM__='{os}';window.__SANDWALK_WINDOW_KIND__={kind};{key_js}{snap_js}{route_js}{overlay}"
    )
}

pub fn attach_window_lifecycle(window: &WebviewWindow, hide_on_close: bool) {
    let win_clone = window.clone();
    let label = window.label().to_string();
    window.on_window_event(move |event| match event {
        tauri::WindowEvent::CloseRequested { api, .. } => {
            if hide_on_close {
                api.prevent_close();
                let _ = win_clone.hide();
            } else {
                unregister_window_backend(&label);
            }
        }
        tauri::WindowEvent::Destroyed => {
            unregister_window_backend(&label);
        }
        tauri::WindowEvent::Resized(_) | tauri::WindowEvent::ScaleFactorChanged { .. } => {
            if let Ok(fullscreen) = win_clone.is_fullscreen() {
                let _ = win_clone.emit("sandwalk-window-fullscreen", fullscreen);
            }
        }
        #[cfg(target_os = "macos")]
        tauri::WindowEvent::Focused(focused) => {
            let _ = win_clone.emit("sandwalk-window-glass-active", *focused);
        }
        _ => {}
    });
}

pub type ApplyGlassFn = fn(&AppHandle, &WebviewWindow);

#[allow(clippy::too_many_arguments)]
pub fn build_sandwalk_window(
    app: &AppHandle,
    label: &str,
    backend_url: &str,
    api_key: Option<&str>,
    title: &str,
    initial_route: Option<&str>,
    snapshot_id: Option<&str>,
    hide_on_close: bool,
    is_spa_route: impl Fn(&str) -> bool,
    apply_glass: Option<ApplyGlassFn>,
) -> Result<WebviewWindow, String> {
    let snap = register_window_backend_with_snapshot(label, backend_url, snapshot_id);
    let route = initial_route
        .map(str::trim)
        .filter(|r| !r.is_empty())
        .unwrap_or("/");
    let script = inject_bootstrap_script(
        Some(route),
        backend_url,
        api_key,
        Some(&snap),
        if label == "main" { "main" } else { "client" },
        is_spa_route,
    );
    let mut win = WebviewWindowBuilder::new(app, label, WebviewUrl::App("index.html".into()))
        .title(title)
        .inner_size(1280.0, 860.0)
        .min_inner_size(900.0, 600.0)
        .disable_drag_drop_handler()
        .initialization_script(&script);

    #[cfg(target_os = "macos")]
    {
        win = win
            .transparent(true)
            .title_bar_style(tauri::TitleBarStyle::Overlay)
            .hidden_title(true)
            .traffic_light_position(tauri::LogicalPosition::new(19.0, 24.0));
    }

    let window = win.build().map_err(|e| e.to_string())?;

    #[cfg(target_os = "macos")]
    if let Some(apply) = apply_glass {
        apply(app, &window);
        let _ = window.emit("sandwalk-window-glass-active", true);
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = apply_glass;
    }

    attach_window_lifecycle(&window, hide_on_close);
    upsert_recent_snapshot(&snap, backend_url, route, title);
    let _ = install_app_menu(app);
    Ok(window)
}

pub fn open_or_focus_window(
    app: &AppHandle,
    args: OpenWindowArgs,
    fallback_url: &str,
    is_spa_route: impl Fn(&str) -> bool + Copy,
    apply_glass: Option<ApplyGlassFn>,
) -> Result<String, String> {
    let url = normalize_url(
        args.backend_url
            .as_deref()
            .filter(|s| !s.trim().is_empty())
            .unwrap_or(fallback_url),
    );
    let route = args
        .route
        .as_deref()
        .map(str::trim)
        .filter(|r| !r.is_empty())
        .unwrap_or("/")
        .to_string();
    let title = args
        .title
        .as_deref()
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .map(|t| t.to_string())
        .unwrap_or_else(|| window_title_for_url(&url));
    let snapshot_id = args
        .snapshot_id
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());

    if args.focus_existing {
        let existing = snapshot_id
            .as_deref()
            .and_then(|id| find_window_for_snapshot(app, id))
            .or_else(|| {
                // Legacy / no snapshot: only focus when a single matching URL exists.
                find_window_for_url(app, &url)
            });
        if let Some(existing) = existing {
            let _ = existing.unminimize();
            let _ = existing.show();
            let _ = existing.set_focus();
            let id = snapshot_id
                .clone()
                .or_else(|| snapshot_id_for_label(existing.label()))
                .unwrap_or_else(new_snapshot_id);
            upsert_recent_snapshot(&id, &url, &route, &title);
            let _ = install_app_menu(app);
            return Ok(existing.label().to_string());
        }
    }

    let label = format!(
        "client-{}-{}",
        now_secs(),
        std::process::id() % 10_000
    );
    let window = build_sandwalk_window(
        app,
        &label,
        &url,
        args.api_key.as_deref(),
        &title,
        Some(&route),
        snapshot_id.as_deref(),
        false,
        is_spa_route,
        apply_glass,
    )?;
    let _ = window.show();
    let _ = window.set_focus();
    Ok(label)
}

fn emit_menu_action(app: &AppHandle, payload: MenuActionPayload) {
    let target = app
        .webview_windows()
        .into_iter()
        .find(|(_, w)| w.is_focused().unwrap_or(false) && w.is_visible().unwrap_or(true))
        .map(|(_, w)| w)
        .or_else(|| app.get_webview_window("main"));
    if let Some(win) = &target {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
        let _ = win.emit("sandwalk-menu", payload);
    } else {
        let _ = app.emit("sandwalk-menu", payload);
    }
}

pub fn install_app_menu(app: &AppHandle) -> Result<(), String> {
    let recents = read_recents();
    let mut recent_menu = SubmenuBuilder::new(app, "Open Recent");
    if recents.is_empty() {
        recent_menu = recent_menu.text("recent-empty", "No Recent Windows");
    } else {
        for (index, row) in recents.iter().enumerate() {
            let id = format!("recent:{index}");
            recent_menu = recent_menu.text(id, recent_menu_label(row));
        }
        recent_menu = recent_menu
            .separator()
            .text("clear-recent", "Clear Recent");
    }
    let recent_submenu = recent_menu.build().map_err(|e| e.to_string())?;

    // First submenu becomes the macOS app menu (named "Sandwalk" by the OS).
    // Without this, File is absorbed and disappears from the menu bar.
    let app_menu = SubmenuBuilder::new(app, "Sandwalk")
        .item(
            &PredefinedMenuItem::about(app, Some("Sandwalk"), None)
                .map_err(|e| e.to_string())?,
        )
        .text("check-updates", "Check for Updates…")
        .separator()
        .text("server-settings", "Server Settings…")
        .separator()
        .item(&PredefinedMenuItem::services(app, None).map_err(|e| e.to_string())?)
        .separator()
        .item(&PredefinedMenuItem::hide(app, None).map_err(|e| e.to_string())?)
        .item(&PredefinedMenuItem::hide_others(app, None).map_err(|e| e.to_string())?)
        .item(&PredefinedMenuItem::show_all(app, None).map_err(|e| e.to_string())?)
        .separator()
        .item(&PredefinedMenuItem::quit(app, None).map_err(|e| e.to_string())?)
        .build()
        .map_err(|e| e.to_string())?;

    let file = SubmenuBuilder::new(app, "File")
        .item(
            &tauri::menu::MenuItemBuilder::with_id("new-window", "New Window")
                .accelerator("CmdOrCtrl+Shift+N")
                .build(app)
                .map_err(|e| e.to_string())?,
        )
        .text("new-window-remote", "New Window (Remote)…")
        .separator()
        .item(&recent_submenu)
        .separator()
        .item(
            &PredefinedMenuItem::close_window(app, Some("Close Window"))
                .map_err(|e| e.to_string())?,
        )
        .build()
        .map_err(|e| e.to_string())?;

    let edit = SubmenuBuilder::new(app, "Edit")
        .undo()
        .redo()
        .separator()
        .cut()
        .copy()
        .paste()
        .select_all()
        .build()
        .map_err(|e| e.to_string())?;

    let window_menu = SubmenuBuilder::new(app, "Window")
        .minimize()
        .maximize()
        .build()
        .map_err(|e| e.to_string())?;

    let menu = MenuBuilder::new(app)
        .item(&app_menu)
        .item(&file)
        .item(&edit)
        .item(&window_menu)
        .build()
        .map_err(|e| e.to_string())?;

    app.set_menu(menu).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn handle_menu_event(
    app: &AppHandle,
    event: &MenuEvent,
    fallback_url: &str,
    is_spa_route: impl Fn(&str) -> bool + Copy,
    apply_glass: Option<ApplyGlassFn>,
) {
    let id = event.id().as_ref();
    match id {
        "new-window" => {
            let url = focused_backend_url(app, fallback_url);
            let _ = open_or_focus_window(
                app,
                OpenWindowArgs {
                    backend_url: Some(url),
                    api_key: None,
                    title: None,
                    route: Some("/".into()),
                    snapshot_id: None,
                    focus_existing: false,
                },
                fallback_url,
                is_spa_route,
                apply_glass,
            );
        }
        "new-window-remote" => {
            emit_menu_action(
                app,
                MenuActionPayload {
                    action: "new-window-remote".into(),
                    url: None,
                    route: None,
                    title: None,
                    snapshot_id: None,
                },
            );
        }
        "check-updates" => {
            emit_menu_action(
                app,
                MenuActionPayload {
                    action: "check-updates".into(),
                    url: None,
                    route: None,
                    title: None,
                    snapshot_id: None,
                },
            );
        }
        "server-settings" => {
            let _ = open_server_settings_app();
        }
        "clear-recent" => {
            clear_recents();
            let _ = install_app_menu(app);
        }
        "recent-empty" => {}
        other if other.starts_with("recent:") => {
            let Ok(index) = other.trim_start_matches("recent:").parse::<usize>() else {
                return;
            };
            let Some(row) = read_recents().into_iter().nth(index) else {
                return;
            };
            let title = display_title(&row);
            let route = if row.route.trim().is_empty() {
                "/".into()
            } else {
                row.route.clone()
            };
            emit_menu_action(
                app,
                MenuActionPayload {
                    action: "open-recent".into(),
                    url: Some(row.url),
                    route: Some(route),
                    title: Some(title),
                    snapshot_id: Some(row.id),
                },
            );
        }
        _ => {}
    }
}

pub fn focus_best_window(app: &AppHandle) {
    let mut visible: Vec<WebviewWindow> = app
        .webview_windows()
        .into_values()
        .filter(|w| w.is_visible().unwrap_or(false))
        .collect();
    visible.sort_by_key(|w| if w.label() == "main" { 1 } else { 0 });
    if let Some(win) = visible.into_iter().next() {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
        return;
    }
    if let Some(win) = app.get_webview_window("main") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
    }
}

/// Open the nested Sandwalk Server helper Settings UI.
pub fn open_server_settings_app() -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        use std::process::Command;
        // Prefer deep link (Server owns sandwalk://).
        if Command::new("open")
            .arg("sandwalk://settings/general")
            .status()
            .map(|s| s.success())
            .unwrap_or(false)
        {
            return Ok(());
        }
        // Fallback: launch nested helper with --open-settings.
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        let helper = exe
            .parent()
            .and_then(|p| p.parent())
            .map(|contents| contents.join("Helpers").join("Sandwalk Server.app"));
        if let Some(app) = helper.filter(|p| p.is_dir()) {
            Command::new("open")
                .args(["-n", "-a"])
                .arg(&app)
                .args(["--args", "--open-settings"])
                .spawn()
                .map_err(|e| e.to_string())?;
            return Ok(());
        }
        return Err("Sandwalk Server helper not found".into());
    }
    #[cfg(not(target_os = "macos"))]
    {
        Err("Server Settings is only available on macOS".into())
    }
}

#[tauri::command]
pub fn desktop_list_window_recents() -> Result<Vec<WindowRecent>, String> {
    Ok(read_recents())
}

#[tauri::command]
pub fn desktop_clear_window_recents(app: AppHandle) -> Result<(), String> {
    clear_recents();
    install_app_menu(&app)
}

/// Upsert the focused window's Open Recent snapshot (route + title).
#[tauri::command]
pub fn desktop_upsert_window_snapshot(
    app: AppHandle,
    window: WebviewWindow,
    snapshot_id: Option<String>,
    url: String,
    route: String,
    title: String,
) -> Result<String, String> {
    let label = window.label().to_string();
    let id = snapshot_id
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string())
        .or_else(|| snapshot_id_for_label(&label))
        .unwrap_or_else(new_snapshot_id);
    register_window_backend_with_snapshot(&label, &url, Some(&id));
    upsert_recent_snapshot(&id, &url, &route, &title);
    install_app_menu(&app)?;
    Ok(id)
}

#[tauri::command]
pub fn desktop_remember_window_recent(app: AppHandle, url: String) -> Result<(), String> {
    // Prefer updating the focused window's existing snapshot when possible.
    if let Some((label, _)) = app
        .webview_windows()
        .into_iter()
        .find(|(_, w)| w.is_focused().unwrap_or(false))
    {
        if let Some(id) = snapshot_id_for_label(label.as_str()) {
            upsert_recent_snapshot(&id, &url, "/", &window_title_for_url(&url));
            return install_app_menu(&app);
        }
    }
    remember_recent(&url);
    install_app_menu(&app)
}
