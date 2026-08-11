//! Probe the local IPv4 /24 for Sandwalk servers on port 8787.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream, UdpSocket};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

const DISCOVER_PORT: u16 = 8787;
const CONNECT_TIMEOUT: Duration = Duration::from_millis(200);
const HTTP_TIMEOUT: Duration = Duration::from_millis(300);
const MAX_IN_FLIGHT: usize = 48;

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LanServerHit {
    pub url: String,
    pub hostname: String,
    pub platform: String,
    pub arch: String,
    pub device_label: String,
    pub auth_required: bool,
    pub version: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DiscoverBody {
    service: Option<String>,
    version: Option<String>,
    hostname: Option<String>,
    platform: Option<String>,
    arch: Option<String>,
    device_label: Option<String>,
    auth_required: Option<bool>,
}

fn local_ipv4s() -> Vec<Ipv4Addr> {
    let mut out = Vec::new();
    // UDP connect does not send packets; OS picks the egress interface.
    if let Ok(sock) = UdpSocket::bind("0.0.0.0:0") {
        if sock.connect("8.8.8.8:80").is_ok() {
            if let Ok(local) = sock.local_addr() {
                if let IpAddr::V4(v4) = local.ip() {
                    if !v4.is_loopback() && !v4.is_unspecified() {
                        out.push(v4);
                    }
                }
            }
        }
    }
    out
}

fn candidates_for(ip: Ipv4Addr) -> Vec<Ipv4Addr> {
    let octets = ip.octets();
    let base = u32::from_be_bytes([octets[0], octets[1], octets[2], 0]);
    (1u32..=254)
        .map(|host| Ipv4Addr::from(base | host))
        .collect()
}

fn probe_ip(client: &reqwest::blocking::Client, ip: Ipv4Addr) -> Option<LanServerHit> {
    let addr = SocketAddr::from((ip, DISCOVER_PORT));
    if TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT).is_err() {
        return None;
    }
    let url = format!("http://{ip}:{DISCOVER_PORT}/v1/discover");
    let resp = client.get(&url).send().ok()?;
    if !resp.status().is_success() {
        return None;
    }
    let body: DiscoverBody = resp.json().ok()?;
    if body.service.as_deref() != Some("sandwalk") {
        return None;
    }
    Some(LanServerHit {
        url: format!("http://{ip}:{DISCOVER_PORT}"),
        hostname: body.hostname.unwrap_or_else(|| ip.to_string()),
        platform: body.platform.unwrap_or_default(),
        arch: body.arch.unwrap_or_default(),
        device_label: body
            .device_label
            .filter(|s| !s.trim().is_empty())
            .unwrap_or_else(|| "Sandwalk".into()),
        auth_required: body.auth_required.unwrap_or(false),
        version: body.version.unwrap_or_default(),
    })
}

fn scan_ips(ips: Vec<Ipv4Addr>) -> Vec<LanServerHit> {
    let client = match reqwest::blocking::Client::builder()
        .timeout(HTTP_TIMEOUT)
        .connect_timeout(CONNECT_TIMEOUT)
        .build()
    {
        Ok(c) => Arc::new(c),
        Err(_) => return Vec::new(),
    };
    let hits: Arc<Mutex<Vec<LanServerHit>>> = Arc::new(Mutex::new(Vec::new()));

    for chunk in ips.chunks(MAX_IN_FLIGHT) {
        let handles: Vec<_> = chunk
            .iter()
            .copied()
            .map(|ip| {
                let client = Arc::clone(&client);
                let hits = Arc::clone(&hits);
                thread::spawn(move || {
                    if let Some(hit) = probe_ip(&client, ip) {
                        if let Ok(mut guard) = hits.lock() {
                            guard.push(hit);
                        }
                    }
                })
            })
            .collect();
        for h in handles {
            let _ = h.join();
        }
    }

    let mut rows = hits.lock().map(|g| g.clone()).unwrap_or_default();
    rows.sort_by(|a, b| {
        let a_local = a.url.contains("127.0.0.1");
        let b_local = b.url.contains("127.0.0.1");
        b_local
            .cmp(&a_local)
            .then_with(|| a.hostname.cmp(&b.hostname))
            .then_with(|| a.url.cmp(&b.url))
    });
    let mut seen = HashSet::new();
    rows.retain(|r| seen.insert(r.url.clone()));
    rows
}

/// Scan localhost + each local /24 for Sandwalk `/v1/discover` on :8787.
pub fn scan_lan_servers() -> Vec<LanServerHit> {
    let mut ips: Vec<Ipv4Addr> = vec![Ipv4Addr::new(127, 0, 0, 1)];
    let mut seen = HashSet::new();
    seen.insert(Ipv4Addr::new(127, 0, 0, 1));
    for local in local_ipv4s() {
        for ip in candidates_for(local) {
            if seen.insert(ip) {
                ips.push(ip);
            }
        }
    }
    scan_ips(ips)
}

/// Run the LAN probe off the async runtime so the dialog can open immediately.
#[tauri::command]
pub async fn desktop_scan_lan_servers() -> Result<Vec<LanServerHit>, String> {
    tauri::async_runtime::spawn_blocking(scan_lan_servers)
        .await
        .map_err(|e| e.to_string())
}
