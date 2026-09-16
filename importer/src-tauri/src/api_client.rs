use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::Path;
use walkdir::WalkDir;

#[derive(Serialize)]
struct RawThreadPayload<'a> {
    thread_id: String,
    raw_json: &'a Value,
}

#[derive(Deserialize)]
struct ImportResult {
    rows_inserted: usize,
    #[allow(dead_code)]
    thread_id: String,
}

pub struct ForwardSummary {
    pub threads_sent: usize,
    pub rows_inserted: usize,
}

/// Tests whether the API at base_url is reachable with the given token.
pub fn test_connection(base_url: &str, token: &str) -> Result<()> {
    let client = reqwest::blocking::Client::new();
    let resp = client
        .get(format!("{base_url}/health"))
        .header("X-API-Key", token)
        .send()
        .context("Could not reach the API")?;

    if resp.status().is_success() {
        Ok(())
    } else {
        anyhow::bail!("API responded with status {}", resp.status())
    }
}

/// Walks all thread JSON files in the extracted directory and posts each one
/// to the matching /import/<platform> endpoint of the API.
pub fn forward_directory(
    base_url: &str,
    token: &str,
    platform: &str,
    extracted_path: &str,
) -> Result<ForwardSummary> {
    let client = reqwest::blocking::Client::new();
    let endpoint = format!("{base_url}/import/{platform}");

    let mut threads_sent = 0usize;
    let mut rows_inserted = 0usize;

    for entry in WalkDir::new(extracted_path)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map(|ext| ext == "json").unwrap_or(false))
    {
        let path: &Path = entry.path();
        let raw = std::fs::read_to_string(path)
            .with_context(|| format!("Could not read {:?}", path))?;
        let json: Value = serde_json::from_str(&raw)
            .with_context(|| format!("{:?} is not valid JSON", path))?;

        // Derive thread_id from the folder name (Meta creates one folder per thread)
        let thread_id = path
            .parent()
            .and_then(|p| p.file_name())
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_else(|| "unknown".to_string());

        let payload = RawThreadPayload { thread_id: thread_id.clone(), raw_json: &json };

        let resp = client
            .post(&endpoint)
            .header("X-API-Key", token)
            .json(&payload)
            .send()
            .with_context(|| format!("Request to {endpoint} failed"))?;

        if !resp.status().is_success() {
            anyhow::bail!("API error ({}) for thread {}", resp.status(), thread_id);
        }

        let result: ImportResult = resp.json()?;
        threads_sent += 1;
        rows_inserted += result.rows_inserted;
    }

    Ok(ForwardSummary { threads_sent, rows_inserted })
}
