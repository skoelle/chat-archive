---
description: Create a new importer release with version bump, commit, tag, and push.
---

Create a release for the importer with version `$ARGUMENTS`.

Follow these steps exactly:

1. **Validate the version argument**: `$ARGUMENTS` must be a semver-like string (e.g. `0.1.0`, `1.2.3`). If empty or invalid, ask the user for a valid version.

2. **Update version in all three files** (use the Edit tool for each):
   - `importer/package.json`: set `"version": "<version>"`
   - `importer/src-tauri/Cargo.toml`: set `version = "<version>"`
   - `importer/src-tauri/tauri.conf.json`: set `"version": "<version>"`

3. **Commit** the version bump:
   ```
   git add importer/package.json importer/src-tauri/Cargo.toml importer/src-tauri/tauri.conf.json
   git commit -m "Release importer v<version>"
   ```

4. **Create and push the tag**:
   ```
   git tag importer-v<version>
   git push origin main && git push origin importer-v<version>
   ```

5. **Report back**: Confirm the tag was pushed and mention that the GitHub Actions workflow will now build the Windows binaries.
