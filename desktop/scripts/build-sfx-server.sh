#!/usr/bin/env sh
# Freezes the Stable Audio Open Small server (desktop/sfx-server/serve.py) into one executable at
# src-tauri/binaries/sfx-server-<target-triple>. stable-audio-tools needs Python 3.10 and torch 2.7.1,
# so it has its own environment and never meets the API sidecar's pins. Needs Python 3.10
# (set SFX_PYTHON to point at it).
set -eu

STABLE_AUDIO_TOOLS="0.0.20"
# Nested build pips must ignore a user-level pip.conf (e.g. require-hashes), which breaks source builds.
export PIP_CONFIG_FILE=/dev/null
DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
OUT="$DESKTOP/src-tauri/binaries"
WORK="$DESKTOP/src-tauri/target/sfx-server"
VENV="$WORK/venv-$STABLE_AUDIO_TOOLS" # one venv per pin, so a new pin never reuses old packages
VERSION="$STABLE_AUDIO_TOOLS+$(shasum "$DESKTOP/sfx-server/serve.py" | cut -c1-8)"
dest="$OUT/sfx-server-$TRIPLE"

if [ -x "$dest" ] && [ "$(cat "$dest.version" 2>/dev/null)" = "$VERSION" ]; then
  echo "sfx-server $VERSION already built"; exit 0
fi

mkdir -p "$WORK"
[ -x "$VENV/bin/python" ] || "${SFX_PYTHON:-python3.10}" -m venv "$VENV"
PY="$VENV/bin/python"
# numpy<2: stable-audio-tools pins PyWavelets 1.4.1, which is built against numpy 1.x.
# pytorch_lightning: imported when the model is built, though the package lists it as a training extra.
"$PY" -m pip install -q "stable-audio-tools==$STABLE_AUDIO_TOOLS" "numpy<2" pytorch_lightning \
  fastapi uvicorn soundfile pyinstaller

"$PY" -m PyInstaller --noconfirm --clean --onefile --name sfx-server \
  --distpath "$WORK/dist" --workpath "$WORK/build" --specpath "$WORK" \
  --collect-all stable_audio_tools --collect-all alias_free_torch --collect-all v_diffusion_pytorch \
  --collect-all vector_quantize_pytorch --collect-all nnAudio --collect-all einops_exts \
  --collect-submodules transformers --collect-submodules pytorch_lightning \
  --copy-metadata transformers --copy-metadata requests --copy-metadata tqdm --copy-metadata regex \
  --copy-metadata packaging --copy-metadata filelock --copy-metadata numpy --copy-metadata tokenizers \
  --copy-metadata huggingface-hub --copy-metadata safetensors --copy-metadata pyyaml \
  --copy-metadata torch --copy-metadata pytorch_lightning --copy-metadata importlib_resources \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan.on \
  "$DESKTOP/sfx-server/serve.py"

mkdir -p "$OUT"
cp "$WORK/dist/sfx-server" "$dest"
echo "$VERSION" > "$dest.version"
echo "built $dest"
