# Move Butler.exe into release/ directory

This commit moves the existing Butler.exe binary into the release/ directory to keep the repository root cleaner and to ensure future artifacts are ignored via .gitignore.

Note: This operation preserves the file contents but moving large binaries may not be ideal via the web API; run locally if you need to preserve reflog/working-tree history exactly.
