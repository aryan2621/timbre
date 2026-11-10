#!/usr/bin/env sh
# Freezes the Python API into one executable and places it where Tauri's
# `externalBin` expects it: src-tauri/binaries/voiceclone-api-<target-triple>.
# macOS / Linux only. Needs the repo venv (`pip install -e '.[dev]'`).
set -eu

DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DESKTOP/.." && pwd)"
TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"

cd "$ROOT"
.venv/bin/python -m PyInstaller --noconfirm --clean --onefile \
  --name voiceclone-api \
  --paths "$ROOT" \
  --distpath "$ROOT/build/sidecar" --workpath "$ROOT/build/pyinstaller" --specpath "$ROOT/build" \
  --collect-submodules app \
  --collect-all soundfile --collect-all librosa \
  --collect-all pocket_tts --copy-metadata pocket-tts \
  --collect-submodules diffusers --copy-metadata diffusers \
  --collect-all torchsde --copy-metadata torchsde \
  --collect-submodules transformers.models.musicgen \
  --copy-metadata transformers --copy-metadata requests --copy-metadata tqdm \
  --copy-metadata regex --copy-metadata packaging --copy-metadata filelock \
  --copy-metadata numpy --copy-metadata tokenizers --copy-metadata huggingface-hub \
  --copy-metadata safetensors --copy-metadata pyyaml \
  --collect-all keyring --copy-metadata keyring \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan.on \
  app/api/server.py

mkdir -p "$DESKTOP/src-tauri/binaries"
cp "$ROOT/build/sidecar/voiceclone-api" "$DESKTOP/src-tauri/binaries/voiceclone-api-$TRIPLE"
echo "Sidecar ready: src-tauri/binaries/voiceclone-api-$TRIPLE"
