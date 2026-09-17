// Copyright (c) 2026 Stefan Koelle (https://stefankoelle.de)
// Licensed under the MIT License. See LICENSE file in project root for details.

use crate::api_client;
use crate::extractor;
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
pub struct ApiConfig {
    pub base_url: String,
    pub token: String,
}

#[derive(Serialize)]
pub struct ForwardResult {
    pub threads_sent: usize,
    pub rows_inserted: usize,
}

#[tauri::command]
pub fn extract_takeout(zip_path: String, platform: String) -> Result<String, String> {
    extractor::extract_zip(&zip_path, &platform).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn forward_to_api(
    extracted_path: String,
    platform: String,
    config: ApiConfig,
) -> Result<ForwardResult, String> {
    let summary = api_client::forward_directory(&config.base_url, &config.token, &platform, &extracted_path)
        .map_err(|e| e.to_string())?;
    Ok(ForwardResult { threads_sent: summary.threads_sent, rows_inserted: summary.rows_inserted })
}

#[tauri::command]
pub fn test_api_connection(config: ApiConfig) -> Result<String, String> {
    api_client::test_connection(&config.base_url, &config.token).map_err(|e| e.to_string())?;
    Ok(format!("Successfully connected to {}", config.base_url))
}
