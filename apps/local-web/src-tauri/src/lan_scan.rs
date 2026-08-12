//! Probe the local IPv4 /24 for Sandwalk servers on common API ports.
//!
//! Results are for **remote** discovery — this machine (loopback + our LAN
//! interface IPs + our hostname) is never returned.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream, UdpSocket};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

/// Default agent API ports (primary + common alternates).
const DISCOVER_PORTS: &[u16] = &[8787, 8789, 8790];
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

fn normalize_hostname(raw: &str) -> String {
    raw.trim().trim_end_matches('.').to_ascii_lowercase()
}

fn hostname_aliases(raw: &str) -> HashSet<String> {
    let mut names = HashSet::new();
    let full = normalize_hostname(raw);
    if full.is_empty() {
        return names;
    }
    names.insert(full.clone());
    if let Some(base) = full.strip_suffix(".local") {
        if !base.is_empty() {
            names.insert(base.to_string());
        }
    } else {
        names.insert(format!("{full}.local"));
    }
    if let Some((base, _)) = full.split_once('.') {
        if !base.is_empty() {
            names.insert(base.to_string());
        }
    }
    names
}

fn local_hostnames() -> HashSet<String> {
    let mut names = HashSet::new();
    if let Ok(out) = std::process::Command::new("hostname").output() {
        if out.status.success() {
            names.extend(hostname_aliases(
                &String::from_utf8_lossy(&out.stdout),
            ));
        }
    }
    #[cfg(target_os = "macos")]
    {
        if let Ok(out) = std::process::Command::new("scutil")
            .args(["--get", "LocalHostName"])
            .output()
        {
            if out.status.success() {
                names.extend(hostname_aliases(
                    &String::from_utf8_lossy(&out.stdout),
                ));
            }
        }
    }
    names
}

/// IPv4 addresses that belong to this machine (never shown as "nearby").
fn local_ipv4s() -> HashSet<Ipv4Addr> {
    let mut out = HashSet::new();
    out.insert(Ipv4Addr::LOCALHOST);
    // UDP connect does not send packets; OS picks the egress interface.
    for dest in ["8.8.8.8:80", "1.1.1.1:80"] {
        if let Ok(sock) = UdpSocket::bind("0.0.0.0:0") {
            if sock.connect(dest).is_ok() {
                if let Ok(local) = sock.local_addr() {
                    if let IpAddr::V4(v4) = local.ip() {
                        if !v4.is_loopback() && !v4.is_unspecified() {
                            out.insert(v4);
                        }
                    }
                }
            }
        }
    }
    out
}

fn hit_ip(url: &str) -> Option<Ipv4Addr> {
    let rest = url
        .strip_prefix("http://")
        .or_else(|| url.strip_prefix("https://"))?;
    let host = rest.split('/').next()?.split(':').next()?;
    host.parse().ok()
}

fn is_self_hit(
    hit: &LanServerHit,
    self_ips: &HashSet<Ipv4Addr>,
    self_hosts: &HashSet<String>,
) -> bool {
    if let Some(ip) = hit_ip(&hit.url) {
        if self_ips.contains(&ip) || ip.is_loopback() {
            return true;
        }
    }
    if hit.url.contains("127.0.0.1") || hit.url.to_ascii_lowercase().contains("localhost") {
        return true;
    }
    !self_hosts.is_empty() && !hostname_aliases(&hit.hostname).is_disjoint(self_hosts)
}

fn candidates_for(ip: Ipv4Addr) -> Vec<Ipv4Addr> {
    let octets = ip.octets();
    let base = u32::from_be_bytes([octets[0], octets[1], octets[2], 0]);
    (1u32..=254)
        .map(|host| Ipv4Addr::from(base | host))
        .collect()
}

fn probe_ip_port(
    client: &reqwest::blocking::Client,
    ip: Ipv4Addr,
    port: u16,
) -> Option<LanServerHit> {
    let addr = SocketAddr::from((ip, port));
    if TcpStream::connect_timeout(&addr, CONNECT_TIMEOUT).is_err() {
        return None;
    }
    let url = format!("http://{ip}:{port}/v1/discover");
    let resp = client.get(&url).send().ok()?;
    if !resp.status().is_success() {
        return None;
    }
    let body: DiscoverBody = resp.json().ok()?;
    if body.service.as_deref() != Some("sandwalk") {
        return None;
    }
    Some(LanServerHit {
        url: format!("http://{ip}:{port}"),
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

fn scan_targets(targets: Vec<(Ipv4Addr, u16)>) -> Vec<LanServerHit> {
    let client = match reqwest::blocking::Client::builder()
        .timeout(HTTP_TIMEOUT)
        .connect_timeout(CONNECT_TIMEOUT)
        .build()
    {
        Ok(c) => Arc::new(c),
        Err(_) => return Vec::new(),
    };
    let hits: Arc<Mutex<Vec<LanServerHit>>> = Arc::new(Mutex::new(Vec::new()));

    for chunk in targets.chunks(MAX_IN_FLIGHT) {
        let handles: Vec<_> = chunk
            .iter()
            .copied()
            .map(|(ip, port)| {
                let client = Arc::clone(&client);
                let hits = Arc::clone(&hits);
                thread::spawn(move || {
                    if let Some(hit) = probe_ip_port(&client, ip, port) {
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

    let self_ips = local_ipv4s();
    let self_hosts = local_hostnames();
    let mut rows = hits.lock().map(|g| g.clone()).unwrap_or_default();
    rows.retain(|hit| !is_self_hit(hit, &self_ips, &self_hosts));
    rows.sort_by(|a, b| {
        a.hostname
            .cmp(&b.hostname)
            .then_with(|| a.url.cmp(&b.url))
    });
    let mut seen = HashSet::new();
    rows.retain(|r| seen.insert(r.url.clone()));
    rows
}

/// Scan each local /24 for Sandwalk `/v1/discover` on 8787 / 8789 / 8790.
/// Excludes this machine (loopback, our LAN IPs, our hostname).
pub fn scan_lan_servers() -> Vec<LanServerHit> {
    let self_ips = local_ipv4s();
    let mut ips: Vec<Ipv4Addr> = Vec::new();
    let mut seen = HashSet::new();
    for local in &self_ips {
        if local.is_loopback() {
            continue;
        }
        for ip in candidates_for(*local) {
            // Do not waste probes on ourselves.
            if self_ips.contains(&ip) {
                continue;
            }
            if seen.insert(ip) {
                ips.push(ip);
            }
        }
    }
    let mut targets = Vec::with_capacity(ips.len() * DISCOVER_PORTS.len());
    for ip in ips {
        for &port in DISCOVER_PORTS {
            targets.push((ip, port));
        }
    }
    scan_targets(targets)
}

/// Friendly short hostname for this machine (Welcome Home “Connect locally”).
pub fn local_hostname_display() -> String {
    let mut candidates: Vec<String> = Vec::new();
    #[cfg(target_os = "macos")]
    {
        if let Ok(out) = std::process::Command::new("scutil")
            .args(["--get", "LocalHostName"])
            .output()
        {
            if out.status.success() {
                let raw = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if !raw.is_empty() {
                    candidates.push(raw);
                }
            }
        }
    }
    if let Ok(out) = std::process::Command::new("hostname").output() {
        if out.status.success() {
            let raw = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !raw.is_empty() {
                candidates.push(raw);
            }
        }
    }
    for raw in candidates {
        let trimmed = raw.trim().trim_end_matches('.');
        let no_local = trimmed
            .strip_suffix(".local")
            .or_else(|| trimmed.strip_suffix(".LOCAL"))
            .unwrap_or(trimmed);
        let short = no_local.split('.').next().unwrap_or(no_local).trim();
        if !short.is_empty() {
            return short.to_string();
        }
    }
    String::new()
}

#[tauri::command]
pub fn desktop_local_hostname() -> String {
    local_hostname_display()
}

/// Run the LAN probe off the async runtime so the dialog can open immediately.
#[tauri::command]
pub async fn desktop_scan_lan_servers() -> Result<Vec<LanServerHit>, String> {
    tauri::async_runtime::spawn_blocking(scan_lan_servers)
        .await
        .map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hostname_aliases_cover_local_suffix() {
        let names = hostname_aliases("Julios-MacBook-Pro.local");
        assert!(names.contains("julios-macbook-pro.local"));
        assert!(names.contains("julios-macbook-pro"));
    }

    #[test]
    fn self_hit_matches_local_ip_and_hostname() {
        let mut ips = HashSet::new();
        ips.insert(Ipv4Addr::new(192, 168, 2, 13));
        ips.insert(Ipv4Addr::LOCALHOST);
        let hosts = hostname_aliases("Julios-MacBook-Pro.local");
        let by_ip = LanServerHit {
            url: "http://192.168.2.13:8787".into(),
            hostname: "other".into(),
            platform: "darwin".into(),
            arch: "arm64".into(),
            device_label: "MacBook Pro".into(),
            auth_required: true,
            version: "0.0.1".into(),
        };
        assert!(is_self_hit(&by_ip, &ips, &hosts));
        let by_host = LanServerHit {
            url: "http://192.168.2.99:8787".into(),
            hostname: "Julios-MacBook-Pro.local".into(),
            platform: "darwin".into(),
            arch: "arm64".into(),
            device_label: "MacBook Pro".into(),
            auth_required: true,
            version: "0.0.1".into(),
        };
        assert!(is_self_hit(&by_host, &ips, &hosts));
        let remote = LanServerHit {
            url: "http://192.168.2.178:8787".into(),
            hostname: "Julios-Mac-mini.local".into(),
            platform: "darwin".into(),
            arch: "arm64".into(),
            device_label: "Mac mini".into(),
            auth_required: true,
            version: "0.0.1".into(),
        };
        assert!(!is_self_hit(&remote, &ips, &hosts));
    }
}
