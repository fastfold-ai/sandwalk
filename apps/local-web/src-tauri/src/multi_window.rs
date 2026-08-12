//! Multi-window File menu, Open Recent, and per-window backend bootstrap.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::image::Image;
use tauri::menu::{
    AboutMetadata, MenuBuilder, MenuEvent, PredefinedMenuItem, SubmenuBuilder,
};

/// Default dark Dock tile (1024×1024 squircle + border) — same asset as dark theme.
static ABOUT_ICON_PNG: &[u8] = include_bytes!("../icons/dock/dock-dark.png");
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
    /// Page / session title only (no host suffix — Open Recent / Dock compose that).
    #[serde(default)]
    pub title: String,
    /// Remote machine hostname from `/v1/discover` (e.g. `Julios-Mac-mini`).
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub hostname: String,
    /// OS family from LAN scan / discover (`Darwin`, `Linux`, `Windows`, …).
    #[serde(default, skip_serializing_if = "String::is_empty")]
    pub platform: String,
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
    /// Friendly remote hostname (from LAN scan / discover).
    pub hostname: Option<String>,
    /// OS from LAN scan / discover — stored on the recent so WelcomeHome need not probe.
    pub platform: Option<String>,
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
    #[serde(skip_serializing_if = "Option::is_none")]
    hostname: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    platform: Option<String>,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ApplyAuthPayload {
    url: String,
    api_key: String,
}

fn apply_auth_script(backend_url: &str, api_key: &str) -> String {
    let http = normalize_url(backend_url);
    let http_js = serde_json::to_string(&http).unwrap_or_else(|_| "\"\"".into());
    let key_js = serde_json::to_string(api_key).unwrap_or_else(|_| "\"\"".into());
    format!(
        r#"try{{
  window.__SANDWALK_HTTP__={http_js};
  window.__SANDWALK_API_KEY__={key_js};
  var prev={{}};
  try{{
    var n=window.name||'';
    if(n.indexOf('sandwalk-bind:')===0)prev=JSON.parse(n.slice(14))||{{}};
  }}catch(e){{}}
  prev.http={http_js};
  prev.apiKey={key_js};
  window.name='sandwalk-bind:'+JSON.stringify(prev);
}}catch(e){{}}"#,
        http_js = http_js,
        key_js = key_js
    )
}

fn apply_auth_to_window(window: &WebviewWindow, backend_url: &str, api_key: Option<&str>) {
    let Some(key) = api_key.map(str::trim).filter(|k| !k.is_empty()) else {
        return;
    };
    let url = normalize_url(backend_url);
    let _ = window.eval(&apply_auth_script(&url, key));
    let _ = window.emit(
        "sandwalk-apply-auth",
        ApplyAuthPayload {
            url,
            api_key: key.to_string(),
        },
    );
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

fn is_local_url(url: &str) -> bool {
    let u = url.to_lowercase();
    u.contains("127.0.0.1") || u.contains("localhost")
}

fn is_generic_title(title: &str) -> bool {
    let t = title.trim();
    t.is_empty() || t.eq_ignore_ascii_case("Sandwalk")
}

fn is_root_route(route: &str) -> bool {
    let r = route.trim();
    r.is_empty() || r == "/"
}

/// Untitled local home windows are noise (dev reloads / New Window spam).
fn is_generic_local_snapshot(url: &str, route: &str, title: &str) -> bool {
    is_local_url(url) && is_root_route(route) && is_generic_title(title)
}

/// Drop duplicate generic-local rows; keep remotes + titled/routed locals.
fn prune_recents(rows: Vec<WindowRecent>) -> (Vec<WindowRecent>, bool) {
    let before_len = rows.len();
    let mut dirty = rows.len() > MAX_RECENTS;
    let mut seen_generic_local = false;
    let mut out = Vec::with_capacity(rows.len().min(MAX_RECENTS));
    for row in rows {
        if is_generic_local_snapshot(&row.url, &row.route, &row.title) {
            if seen_generic_local {
                dirty = true;
                continue;
            }
            seen_generic_local = true;
            let mut kept = row;
            if kept.id != "local" || kept.title != "Local" {
                dirty = true;
                kept.id = "local".into();
                kept.title = "Local".into();
            }
            out.push(kept);
            continue;
        }
        out.push(row);
    }
    if out.len() > MAX_RECENTS {
        dirty = true;
        out.truncate(MAX_RECENTS);
    }
    if out.len() != before_len {
        dirty = true;
    }
    (out, dirty)
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
            row.title = "Sandwalk".into();
            dirty = true;
        }
        // Strip host suffixes baked into title by older builds.
        let cleaned = page_title_only(&row.title, &row.url, &row.hostname);
        if cleaned != row.title {
            row.title = cleaned;
            dirty = true;
        }
    }
    let (pruned, pruned_dirty) = prune_recents(rows);
    rows = pruned;
    if dirty || pruned_dirty {
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

/// Notify every WebView that `window-recents.json` changed (WelcomeHome list).
fn emit_recents_changed(app: &AppHandle) {
    let _ = app.emit("sandwalk-window-recents-changed", ());
}

fn hostport_from_url(url: &str) -> Option<String> {
    let url = normalize_url(url);
    if url.contains("127.0.0.1") || url.to_lowercase().contains("localhost") {
        return None;
    }
    let rest = url
        .strip_prefix("https://")
        .or_else(|| url.strip_prefix("http://"))
        .unwrap_or(&url);
    let hostport = rest.split('/').next().unwrap_or(rest);
    if hostport.is_empty() {
        None
    } else {
        Some(hostport.to_string())
    }
}

fn short_hostname(raw: &str) -> String {
    let t = raw.trim();
    if t.is_empty() {
        return String::new();
    }
    t.strip_suffix(".local")
        .unwrap_or(t)
        .split('.')
        .next()
        .unwrap_or(t)
        .to_string()
}

/// Page title without a previously baked-in ` — host` suffix (legacy rows).
fn page_title_only(title: &str, url: &str, hostname: &str) -> String {
    let mut out = title.trim().to_string();
    if out.is_empty() {
        return "Sandwalk".into();
    }
    let mut suffixes = Vec::new();
    if let Some(hp) = hostport_from_url(url) {
        suffixes.push(hp.clone());
        if let Some((host, _)) = hp.split_once(':') {
            suffixes.push(host.to_string());
        }
    }
    let short = short_hostname(hostname);
    if !short.is_empty() {
        suffixes.push(short);
    }
    if !hostname.trim().is_empty() {
        suffixes.push(hostname.trim().to_string());
    }
    for suffix in suffixes {
        for sep in [" — ", " - ", " · "] {
            let needle = format!("{sep}{suffix}");
            if let Some(stripped) = out.strip_suffix(&needle) {
                out = stripped.trim_end().to_string();
            }
        }
    }
    if out.is_empty() {
        "Sandwalk".into()
    } else {
        out
    }
}

fn display_title(row: &WindowRecent) -> String {
    let title = page_title_only(&row.title, &row.url, &row.hostname);
    if !title.is_empty() && title != "Sandwalk" {
        return title;
    }
    if let Some(label) = row.label.as_deref().map(str::trim).filter(|s| !s.is_empty()) {
        return label.to_string();
    }
    if title.is_empty() {
        "Sandwalk".into()
    } else {
        title
    }
}

/// Open Recent: `Hello — Julios-Mac-mini · 192.168.2.178:8787` (hostname + IP when both).
fn recent_menu_label(row: &WindowRecent) -> String {
    let title = display_title(row);
    let Some(hostport) = hostport_from_url(&row.url) else {
        // Local: show session/page title, or "Local" for the placeholder.
        if title.eq_ignore_ascii_case("Sandwalk") || title.eq_ignore_ascii_case("Local") {
            return "Local".into();
        }
        return title;
    };
    let short = short_hostname(&row.hostname);
    let ip_part = hostport
        .split_once(':')
        .map(|(h, _)| h)
        .unwrap_or(&hostport);
    if !short.is_empty() && !short.eq_ignore_ascii_case(ip_part) {
        return format!("{title} — {short} · {hostport}");
    }
    format!("{title} — {hostport}")
}

fn normalize_platform(raw: Option<&str>) -> String {
    raw.map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("")
        .to_string()
}

fn local_platform() -> String {
    match std::env::consts::OS {
        "macos" => "Darwin".into(),
        "windows" => "Windows".into(),
        other => {
            // "linux", etc. — match `/v1/discover` platform.system() style.
            let mut chars = other.chars();
            match chars.next() {
                Some(c) => format!("{}{}", c.to_ascii_uppercase(), chars.as_str()),
                None => other.into(),
            }
        }
    }
}

/// Upsert a window snapshot into Open Recent (keyed by snapshot id).
pub fn upsert_recent_snapshot(
    snapshot_id: &str,
    url: &str,
    route: &str,
    title: &str,
    hostname: Option<&str>,
    platform: Option<&str>,
) {
    let url = normalize_url(url);
    let route = {
        let t = route.trim();
        if t.is_empty() { "/" } else { t }
    }
    .to_string();
    let hostname = hostname
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(short_hostname)
        .unwrap_or_default();
    let platform = normalize_platform(platform);
    let title = {
        let t = page_title_only(title, &url, &hostname);
        if t.is_empty() {
            "Sandwalk".into()
        } else {
            t
        }
    };

    // Skip spam: untitled local home windows (dev reload / blank New Window).
    // Remotes always record — even with a generic title — so the menu shows host · IP.
    if is_generic_local_snapshot(&url, &route, &title) {
        let mut rows = read_recents();
        rows.retain(|r| !is_generic_local_snapshot(&r.url, &r.route, &r.title) && r.id != "local");
        rows.insert(
            0,
            WindowRecent {
                id: "local".into(),
                url,
                route,
                title: "Local".into(),
                hostname: String::new(),
                platform: local_platform(),
                label: None,
                last_opened_at: now_secs(),
            },
        );
        rows.truncate(MAX_RECENTS);
        let _ = write_recents(&rows);
        return;
    }

    let id = if snapshot_id.trim().is_empty() {
        new_snapshot_id()
    } else if snapshot_id == "main" && is_local_url(&url) && is_root_route(&route) && is_generic_title(&title)
    {
        "local".into()
    } else {
        snapshot_id.trim().to_string()
    };
    let mut rows = read_recents();
    // Keep previously learned hostname / platform when this upsert omits them.
    let prior = rows
        .iter()
        .find(|r| r.id == id || normalize_url(&r.url) == url)
        .cloned();
    let hostname = if hostname.is_empty() {
        prior
            .as_ref()
            .map(|r| r.hostname.clone())
            .filter(|h| !h.is_empty())
            .unwrap_or_default()
    } else {
        hostname
    };
    let platform = if platform.is_empty() {
        prior
            .as_ref()
            .map(|r| r.platform.clone())
            .filter(|p| !p.is_empty())
            .unwrap_or_else(|| {
                if is_local_url(&url) {
                    local_platform()
                } else {
                    String::new()
                }
            })
    } else {
        platform
    };
    rows.retain(|r| {
        r.id != id
            && !(r.id.is_empty() && normalize_url(&r.url) == url && r.route == route)
            && !is_generic_local_snapshot(&r.url, &r.route, &r.title)
    });
    rows.insert(
        0,
        WindowRecent {
            id,
            url,
            route,
            title,
            hostname,
            platform,
            label: None,
            last_opened_at: now_secs(),
        },
    );
    rows.truncate(MAX_RECENTS);
    let _ = write_recents(&rows);
}

/// Legacy helper — records a bare server entry (no route/title yet).
pub fn remember_recent(url: &str) {
    let url = normalize_url(url);
    if is_local_url(&url) {
        upsert_recent_snapshot("local", &url, "/", "Local", None, Some(&local_platform()));
        return;
    }
    upsert_recent_snapshot(&new_snapshot_id(), &url, "/", "Sandwalk", None, None);
}

pub fn clear_recents() {
    let _ = write_recents(&[]);
}

pub fn window_title_for_url(url: &str) -> String {
    window_title_for_remote(url, None)
}

/// Dock / cold-start title. Prefer hostname over raw IP when known.
pub fn window_title_for_remote(url: &str, hostname: Option<&str>) -> String {
    let url = normalize_url(url);
    if url.contains("127.0.0.1") || url.to_lowercase().contains("localhost") {
        return "Sandwalk".into();
    }
    let hostport = hostport_from_url(&url).unwrap_or_else(|| url.clone());
    let ip = hostport
        .split_once(':')
        .map(|(h, _)| h)
        .unwrap_or(&hostport);
    let short = hostname
        .map(short_hostname)
        .filter(|s| !s.is_empty() && !s.eq_ignore_ascii_case(ip));
    if let Some(name) = short {
        return format!("Sandwalk — {name}");
    }
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

/// Percent-encode for WebView bootstrap query params.
fn pct_encode(raw: &str) -> String {
    let mut out = String::with_capacity(raw.len() * 3);
    for b in raw.bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(b as char);
            }
            _ => out.push_str(&format!("%{b:02X}")),
        }
    }
    out
}

/// App URL with per-window bind in the query string (survives shared localStorage).
fn window_start_url(
    backend_url: &str,
    api_key: Option<&str>,
    snapshot_id: &str,
) -> WebviewUrl {
    let http = normalize_url(backend_url);
    let mut path = format!(
        "index.html?sw_http={}&sw_snap={}",
        pct_encode(&http),
        pct_encode(snapshot_id)
    );
    if let Some(key) = api_key.map(str::trim).filter(|k| !k.is_empty()) {
        path.push_str(&format!("&sw_key={}", pct_encode(key)));
    }
    WebviewUrl::App(path.into())
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
    let snap = snapshot_id.map(str::trim).filter(|s| !s.is_empty());
    let snap_js = snap
        .map(|s| {
            format!(
                "window.__SANDWALK_SNAPSHOT_ID__={};",
                serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into())
            )
        })
        .unwrap_or_default();
    let http_val = normalize_url(backend_url);
    let http = serde_json::to_string(&http_val)
        .unwrap_or_else(|_| format!("\"{DEFAULT_API}\""));
    let kind = serde_json::to_string(window_kind).unwrap_or_else(|_| "\"client\"".into());
    let key_raw = api_key.map(str::trim).filter(|k| !k.is_empty());
    let key_js = key_raw
        .map(|k| {
            format!(
                "window.__SANDWALK_API_KEY__={};",
                serde_json::to_string(k).unwrap_or_else(|_| "\"\"".into())
            )
        })
        .unwrap_or_default();
    // window.name is per-WebView (unlike shared localStorage/sessionStorage).
    let bind_name = serde_json::json!({
        "http": http_val,
        "apiKey": key_raw.unwrap_or(""),
        "snap": snap.unwrap_or(""),
    });
    let bind_js = format!(
        "try{{window.name='sandwalk-bind:'+{};}}catch(e){{}}",
        serde_json::to_string(&bind_name.to_string()).unwrap_or_else(|_| "\"{}\"".into())
    );
    format!(
        "window.__SANDWALK_HTTP__={http};window.__SANDWALK_PLATFORM__='{os}';window.__SANDWALK_WINDOW_KIND__={kind};{key_js}{snap_js}{route_js}{bind_js}{overlay}"
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
    hostname: Option<&str>,
    platform: Option<&str>,
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
    let start_url = window_start_url(backend_url, api_key, &snap);
    let mut win = WebviewWindowBuilder::new(app, label, start_url)
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

    // Belt-and-suspenders: re-apply bind after the WebView exists (covers cases
    // where initialization_script is skipped for the first navigation).
    let _ = window.eval(&script);

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
    // Only seed Open Recent for remotes (or non-generic titles). Blank local
    // windows are recorded later by the SPA once a real session/page title exists.
    if !is_generic_local_snapshot(backend_url, route, title) {
        upsert_recent_snapshot(&snap, backend_url, route, title, hostname, platform);
        emit_recents_changed(app);
    }
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
    let hostname = args
        .hostname
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    let platform = args
        .platform
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(|s| s.to_string());
    let title = args
        .title
        .as_deref()
        .map(str::trim)
        .filter(|t| !t.is_empty())
        .map(|t| t.to_string())
        .unwrap_or_else(|| window_title_for_remote(&url, hostname.as_deref()));
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
            apply_auth_to_window(&existing, &url, args.api_key.as_deref());
            let id = snapshot_id
                .clone()
                .or_else(|| snapshot_id_for_label(existing.label()))
                .unwrap_or_else(new_snapshot_id);
            upsert_recent_snapshot(
                &id,
                &url,
                &route,
                &title,
                hostname.as_deref(),
                platform.as_deref(),
            );
            emit_recents_changed(app);
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
        hostname.as_deref(),
        platform.as_deref(),
        false,
        is_spa_route,
        apply_glass,
    )?;
    let _ = window.show();
    let _ = window.set_focus();
    apply_auth_to_window(&window, &url, args.api_key.as_deref());
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
    // Native About panel (orderFrontStandardAboutPanel) — same window chrome
    // Unsloth uses (traffic lights), not an in-webview modal.
    let about_icon = Image::from_bytes(ABOUT_ICON_PNG)
        .ok()
        .or_else(|| app.default_window_icon().cloned());
    // ApplicationVersion shows as the main line; Version (build) is the
    // parenthetical. Leaving short_version unset falls back to Info.plist
    // CFBundleVersion and duplicates the same number — pass "" to hide it.
    let about = AboutMetadata {
        name: Some("Sandwalk".into()),
        version: Some(format!("Version {}", env!("CARGO_PKG_VERSION"))),
        short_version: Some(String::new()),
        copyright: Some("© 2026 Fastfold AI Labs. All rights reserved.".into()),
        authors: Some(vec!["Fastfold AI Labs".into()]),
        icon: about_icon,
        ..Default::default()
    };
    let app_menu = SubmenuBuilder::new(app, "Sandwalk")
        .item(
            &PredefinedMenuItem::about(app, Some("About Sandwalk"), Some(about))
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
            // Welcome / connection chooser — do not bind to the focused
            // window's backend. Cold start on `main` still restores last session.
            let _ = open_or_focus_window(
                app,
                OpenWindowArgs {
                    backend_url: Some(normalize_url(fallback_url)),
                    api_key: None,
                    title: Some("Sandwalk".into()),
                    route: Some("/".into()),
                    snapshot_id: None,
                    hostname: None,
                    platform: None,
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
                    hostname: None,
                    platform: None,
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
                    hostname: None,
                    platform: None,
                },
            );
        }
        "server-settings" => {
            let _ = open_server_settings_app();
        }
        "clear-recent" => {
            clear_recents();
            emit_recents_changed(app);
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
            let hostname = row.hostname.trim().to_string();
            let platform = row.platform.trim().to_string();
            emit_menu_action(
                app,
                MenuActionPayload {
                    action: "open-recent".into(),
                    url: Some(row.url),
                    route: Some(route),
                    title: Some(title),
                    snapshot_id: Some(row.id),
                    hostname: (!hostname.is_empty()).then_some(hostname),
                    platform: (!platform.is_empty()).then_some(platform),
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
    emit_recents_changed(&app);
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
    hostname: Option<String>,
    platform: Option<String>,
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
    upsert_recent_snapshot(
        &id,
        &url,
        &route,
        &title,
        hostname.as_deref(),
        platform.as_deref(),
    );
    emit_recents_changed(&app);
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
            upsert_recent_snapshot(&id, &url, "/", "Sandwalk", None, None);
            emit_recents_changed(&app);
            return install_app_menu(&app);
        }
    }
    remember_recent(&url);
    emit_recents_changed(&app);
    install_app_menu(&app)
}
