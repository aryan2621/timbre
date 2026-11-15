#!/usr/bin/env sh
# Freezes the Python API into a folder (onedir) at src-tauri/resources/voiceclone-api/, which Tauri ships
# as a resource. Onedir starts in about a second instead of unpacking hundreds of MB to a temp dir on
# every launch the way --onefile does.
# macOS / Linux only. Needs the repo venv (`pip install -e '.[dev]'`).
set -eu

DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$DESKTOP/.." && pwd)"

cd "$ROOT"
.venv/bin/python -m PyInstaller --noconfirm --clean --onedir \
  --name voiceclone-api \
  --paths "$ROOT" \
  --distpath "$ROOT/build/sidecar" --workpath "$ROOT/build/pyinstaller" --specpath "$ROOT/build" \
  --collect-submodules app \
  --add-data "$ROOT/app/vendor/underdog_woof/respell.tsv:app/vendor/underdog_woof" \
  --add-data "$ROOT/app/data/engines.json:app/data" \
  --collect-all soundfile --collect-all librosa \
  --collect-all pocket_tts --copy-metadata pocket-tts \
  --collect-all f5_tts --collect-all vocos --collect-all x_transformers --collect-all ema_pytorch --copy-metadata f5-tts \
  --collect-submodules diffusers --copy-metadata diffusers \
  --collect-all torchsde --copy-metadata torchsde \
  --collect-submodules transformers \
  --collect-all chatterbox --collect-all perth --copy-metadata chatterbox-tts \
  --collect-all s3tokenizer --collect-all conformer --copy-metadata resemble-perth --copy-metadata s3tokenizer --copy-metadata conformer \
  --copy-metadata transformers --copy-metadata requests --copy-metadata tqdm \
  --copy-metadata regex --copy-metadata packaging --copy-metadata filelock \
  --copy-metadata numpy --copy-metadata tokenizers --copy-metadata huggingface-hub \
  --copy-metadata safetensors --copy-metadata pyyaml \
  --collect-all keyring --copy-metadata keyring \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan.on \
  app/api/server.py

RES="$DESKTOP/src-tauri/resources/voiceclone-api"
rm -rf "$RES"
mkdir -p "$DESKTOP/src-tauri/resources"
cp -R "$ROOT/build/sidecar/voiceclone-api" "$RES"
echo "Sidecar ready: src-tauri/resources/voiceclone-api/"
