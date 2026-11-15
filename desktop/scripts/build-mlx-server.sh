#!/usr/bin/env sh
# Freezes mlx-audio's OpenAI-style speech server (desktop/mlx-server/serve.py) into one executable at
# src-tauri/binaries/mlx-audio-server-<target-triple>. It has its own Python environment so its pins
# (transformers, mlx) never meet the ones in the API sidecar. Apple Silicon only. Needs Python 3.10+.
set -eu

# 0.6.5 on PyPI predates ZONOS3-Mini, so this pins a GitHub commit (2026-11-14).
MLX_AUDIO_COMMIT="b5fcbe964b9e4cad4b06782f97d3e51fe74a8702"
SPACY_MODEL="https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
SPACY_SHA256="1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85"
# Nested build pips must ignore a user-level pip.conf (e.g. require-hashes), which breaks source builds.
export PIP_CONFIG_FILE=/dev/null
DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
OUT="$DESKTOP/src-tauri/binaries"
WORK="$DESKTOP/src-tauri/target/mlx-server"
VENV="$WORK/venv-$(echo "$MLX_AUDIO_COMMIT" | cut -c1-8)" # one venv per pin, so a new pin never reuses old packages
VERSION="$MLX_AUDIO_COMMIT+$(shasum "$DESKTOP/mlx-server/serve.py" | cut -c1-8)"
dest="$OUT/mlx-audio-server-$TRIPLE"

if [ "$(uname -s)-$(uname -m)" != "Darwin-arm64" ]; then
  echo "mlx-audio-server is Apple Silicon only" >&2; exit 1
fi
if [ -x "$dest" ] && [ "$(cat "$dest.version" 2>/dev/null)" = "$VERSION" ]; then
  echo "mlx-audio-server $VERSION already built"; exit 0
fi

[ -x "$VENV/bin/python" ] || "${MLX_PYTHON:-python3}" -m venv "$VENV"
PY="$VENV/bin/python"
# misaki[en] and the spaCy model: Kokoro's text front end downloads the model at first use otherwise,
# which hangs when offline.
"$PY" -m pip install -q "mlx-audio[server] @ git+https://github.com/Blaizzy/mlx-audio@$MLX_AUDIO_COMMIT" "misaki[en]" pyinstaller
echo "$SPACY_MODEL --hash=sha256:$SPACY_SHA256" > "$WORK/spacy-model.txt"
"$PY" -m pip install -q --no-deps -r "$WORK/spacy-model.txt"

"$PY" -m PyInstaller --noconfirm --clean --onefile --name mlx-audio-server \
  --distpath "$WORK/dist" --workpath "$WORK/build" --specpath "$WORK" \
  --collect-all mlx --collect-all mlx_audio --collect-all misaki --collect-all spacy \
  --collect-all en_core_web_sm --collect-all espeakng_loader --collect-all language_tags \
  --copy-metadata mlx-audio --copy-metadata tqdm --copy-metadata regex --copy-metadata requests \
  --copy-metadata packaging --copy-metadata filelock --copy-metadata numpy --copy-metadata tokenizers \
  --copy-metadata huggingface-hub --copy-metadata safetensors --copy-metadata pyyaml \
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan.on \
  "$DESKTOP/mlx-server/serve.py"

mkdir -p "$OUT"
cp "$WORK/dist/mlx-audio-server" "$dest"
echo "$VERSION" > "$dest.version"
echo "built $dest"
