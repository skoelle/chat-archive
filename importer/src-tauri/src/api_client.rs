// Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
// Licensed under the MIT License. See LICENSE file in project root for details.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
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

/// Walks all thread JSON files in the extracted directory, groups them by
/// parent directory, and posts each thread to the matching /import/<platform>
/// endpoint of the API.
///
/// - Instagram / Facebook normal: thread directories contain `message_*.json`
///   files (possibly split across multiple files). All files in a directory
///   are combined into a single request; `thread_id` = directory name.
/// - Facebook E2EE: flat structure, each `.json` file is its own thread.
///   `thread_id` = file name without extension.
pub fn forward_directory(
    base_url: &str,
    token: &str,
    platform: &str,
    extracted_path: &str,
) -> Result<ForwardSummary> {
    let client = reqwest::blocking::Client::new();
    let endpoint = format!("{base_url}/import/{platform}");

    // 1. Collect all JSON files grouped by parent directory
    let mut groups: HashMap<PathBuf, Vec<PathBuf>> = HashMap::new();

    for entry in WalkDir::new(extracted_path)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map(|ext| ext == "json").unwrap_or(false))
        .filter(|e| {
            let path_str = e.path().to_string_lossy();
            if platform == "instagram" {
                return path_str.contains("/messages/inbox/");
            }
            if platform == "facebook" {
                if path_str.contains("/messages/message_requests/")
                    || path_str.contains("/messages/filtered_threads/")
                {
                    return false;
                }
            }
            true
        })
    {
        let path = entry.into_path();
        let parent = path
            .parent()
            .unwrap_or(Path::new(extracted_path))
            .to_path_buf();
        groups.entry(parent).or_default().push(path);
    }

    let mut threads_sent = 0usize;
    let mut rows_inserted = 0usize;

    // 2. Process each group
    for (dir, files) in &groups {
        let has_message_files = files.iter().any(|f| {
            f.file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.starts_with("message_"))
                .unwrap_or(false)
        });

        if has_message_files {
            // Instagram / Facebook normal: combine all message_*.json files
            let thread_id = dir
                .file_name()
                .map(|n| n.to_string_lossy().to_string())
                .unwrap_or_else(|| "unknown".to_string());

            let mut combined_messages: Vec<Value> = Vec::new();
            let mut participants: Option<Value> = None;

            for file in files {
                let raw = std::fs::read_to_string(file)
                    .with_context(|| format!("Could not read {:?}", file))?;
                let json: Value = serde_json::from_str(&raw)
                    .with_context(|| format!("{:?} is not valid JSON", file))?;

                if participants.is_none() {
                    participants = json.get("participants").cloned();
                }
                if let Some(msgs) = json.get("messages").and_then(|m| m.as_array()) {
                    combined_messages.extend(msgs.iter().cloned());
                }
            }

            let mut combined_json = serde_json::json!({ "messages": combined_messages });
            if let Some(p) = participants {
                combined_json["participants"] = p;
            }

            let payload = RawThreadPayload {
                thread_id: thread_id.clone(),
                raw_json: &combined_json,
            };

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
        } else {
            // Facebook E2EE: each file is its own thread
            for file in files {
                let thread_id = file
                    .file_stem()
                    .and_then(|n| n.to_str())
                    .map(|n| n.to_string())
                    .unwrap_or_else(|| "unknown".to_string());

                let raw = std::fs::read_to_string(file)
                    .with_context(|| format!("Could not read {:?}", file))?;
                let json: Value = serde_json::from_str(&raw)
                    .with_context(|| format!("{:?} is not valid JSON", file))?;

                let payload = RawThreadPayload {
                    thread_id: thread_id.clone(),
                    raw_json: &json,
                };

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
        }
    }

    Ok(ForwardSummary { threads_sent, rows_inserted })
}
