# ============================================================
# .clineignore — CarDealersPro
# ------------------------------------------------------------
# Prevents Cline from reading heavy / binary / generated files.
# Keeps the agent focused on source code, configs, and docs.
#
# Format = .gitignore syntax:
#   folder/     → ignore whole directory
#   *.ext       → ignore by extension
#   !keep.txt   → exception (keep this file)
#   # comment   → note
# ============================================================


# ────────────────────────────────────────────────────────────
# 1. Python runtime artifacts
# ────────────────────────────────────────────────────────────
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
.eggs/
pip-wheel-metadata/


# ────────────────────────────────────────────────────────────
# 2. Virtual environments
# ────────────────────────────────────────────────────────────
venv/
.venv/
env/
ENV/
pythonenv*/


# ────────────────────────────────────────────────────────────
# 3. ML / DL artifacts (weights, checkpoints, serialized models)
# ────────────────────────────────────────────────────────────
*.pt
*.pth
*.ckpt
*.onnx
*.h5
*.hdf5
*.pb
*.tflite
*.safetensors
*.bin
*.pkl
*.pickle
*.joblib
*.npy
*.npz
*.msgpack
*.model
*.weights
checkpoints/
runs/
tensorboard/
wandb/
mlruns/
lightning_logs/


# ────────────────────────────────────────────────────────────
# 4. Data files (CSV / Parquet / Arrow / spreadsheets)
# ────────────────────────────────────────────────────────────
*.csv
*.tsv
*.parquet
*.feather
*.arrow
*.jsonl
*.orc
*.avro
*.xlsx
*.xls
data/
data_backup.sql


# ────────────────────────────────────────────────────────────
# 5. Stored user content & on-disk model artifacts
# ────────────────────────────────────────────────────────────
ai_models/
storage/
uploads/
media/


# ────────────────────────────────────────────────────────────
# 6. Images
# ────────────────────────────────────────────────────────────
*.jpg
*.jpeg
*.png
*.gif
*.bmp
*.tiff
*.tif
*.webp
*.ico
*.heic
*.heif
*.svg
*.psd
*.ai


# ────────────────────────────────────────────────────────────
# 7. Videos
# ────────────────────────────────────────────────────────────
*.mp4
*.avi
*.mov
*.mkv
*.webm
*.wmv
*.flv
*.m4v
*.mpg
*.mpeg


# ────────────────────────────────────────────────────────────
# 8. Audio
# ────────────────────────────────────────────────────────────
*.wav
*.mp3
*.flac
*.ogg
*.m4a
*.aac


# ────────────────────────────────────────────────────────────
# 9. Archives & binaries
# ────────────────────────────────────────────────────────────
*.zip
*.tar
*.tar.gz
*.tar.bz2
*.tgz
*.rar
*.7z
*.iso
*.dmg
*.exe
*.msi
*.deb
*.rpm


# ────────────────────────────────────────────────────────────
# 10. Local databases
# ────────────────────────────────────────────────────────────
*.db
*.sqlite
*.sqlite3
*.sqlite-journal
*.db-wal
*.db-shm


# ────────────────────────────────────────────────────────────
# 11. Logs
# ────────────────────────────────────────────────────────────
*.log
logs/
log/
elk/logs/


# ────────────────────────────────────────────────────────────
# 12. ELK stack runtime data (huge, auto-generated)
# ────────────────────────────────────────────────────────────
elk/
filebeat_data/


# ────────────────────────────────────────────────────────────
# 13. Environment files & secrets (DO NOT LET THE AGENT READ)
# ────────────────────────────────────────────────────────────
.env
.env.local
.env.*.local
*.pem
private_base64.txt
public_base64.txt
secrets/
*.key
*.crt

# NOTE: .env.example is intentionally NOT ignored — it is a template.


# ────────────────────────────────────────────────────────────
# 14. Testing & type-checking caches
# ────────────────────────────────────────────────────────────
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
.nox/
.coverage
.coverage.*
htmlcov/
coverage.xml


# ────────────────────────────────────────────────────────────
# 15. Build artifacts
# ────────────────────────────────────────────────────────────
build/
dist/
*.egg
wheelhouse/


# ────────────────────────────────────────────────────────────
# 16. Frontend (Node / JS) — ignore if you never build a UI here
# ────────────────────────────────────────────────────────────
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*
.next/
.nuxt/
.vuepress/dist/
.npm/
.pnp.*


# ────────────────────────────────────────────────────────────
# 17. IDE / editor files
# ────────────────────────────────────────────────────────────
.vscode/
.idea/
*.swp
*.swo
*~
*.sublime-project
*.sublime-workspace


# ────────────────────────────────────────────────────────────
# 18. OS junk
# ────────────────────────────────────────────────────────────
.DS_Store
Thumbs.db
desktop.ini


# ────────────────────────────────────────────────────────────
# 19. Repomix / AI tooling outputs
# ────────────────────────────────────────────────────────────
repomix-output/
repomix-summary/
repomix.xml
*.clineignore-cache/


# ────────────────────────────────────────────────────────────
# 20. Temporary / backup / screenshots
# ────────────────────────────────────────────────────────────
*.tmp
*.bak
*.orig
*.rej
*~
screenshots/
downloads/