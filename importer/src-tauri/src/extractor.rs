use anyhow::{Context, Result};
use std::fs;
use std::path::PathBuf;

/// Extracts the given ZIP file to %TEMP%/takeout-message-importer/<platform>/
pub fn extract_zip(zip_path: &str, platform: &str) -> Result<String> {
    let file = fs::File::open(zip_path).context("Could not open ZIP file")?;
    let mut archive = zip::ZipArchive::new(file).context("ZIP is invalid or corrupted")?;

    let mut target_dir: PathBuf = std::env::temp_dir();
    target_dir.push("takeout-message-importer");
    target_dir.push(platform);

    if target_dir.exists() {
        fs::remove_dir_all(&target_dir).ok();
    }
    fs::create_dir_all(&target_dir)?;

    for i in 0..archive.len() {
        let mut entry = archive.by_index(i)?;
        let out_path = match entry.enclosed_name() {
            Some(p) => target_dir.join(p),
            None => continue,
        };

        if entry.name().ends_with('/') {
            fs::create_dir_all(&out_path)?;
        } else {
            if let Some(parent) = out_path.parent() {
                fs::create_dir_all(parent)?;
            }
            let mut out_file = fs::File::create(&out_path)?;
            std::io::copy(&mut entry, &mut out_file)?;
        }
    }

    Ok(target_dir.to_string_lossy().to_string())
}
