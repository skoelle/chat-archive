mod commands;
mod extractor;
mod api_client;

use commands::{extract_takeout, forward_to_api, test_api_connection};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            extract_takeout,
            forward_to_api,
            test_api_connection
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
