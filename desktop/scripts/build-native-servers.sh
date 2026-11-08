#!/usr/bin/env sh
# Builds llama.cpp's server and whisper.cpp's server as static binaries and places them where
# Tauri bundles sidecars: src-tauri/binaries/<name>-<target-triple>. Users install nothing.
# macOS gets Metal with shaders embedded; Linux gets a portable CPU build. Needs cmake.
set -eu

LLAMA_VERSION="b6000"
WHISPER_VERSION="v1.7.6"
ACE_COMMIT="07abf07da3a9c1c45bd85aabed401644f8eb7c72"
DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
TRIPLE="$(rustc -vV | sed -n 's/^host: //p')"
OUT="$DESKTOP/src-tauri/binaries"
CACHE="$DESKTOP/src-tauri/target/native"
command -v cmake >/dev/null || { echo "cmake is required (macOS: brew install cmake)" >&2; exit 1; }

if [ "$(uname -s)" = "Darwin" ]; then
  PLATFORM="-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON"
  JOBS="$(sysctl -n hw.ncpu)"
else
  PLATFORM="-DGGML_METAL=OFF"
  JOBS="$(nproc)"
fi

build() {
  name="$1"; repo="$2"; version="$3"; target="$4"; extra="$5"
  dest="$OUT/$name-$TRIPLE"
  if [ -x "$dest" ] && [ "$(cat "$dest.version" 2>/dev/null)" = "$version" ]; then
    echo "$name $version already built"
    return
  fi
  src="$CACHE/$name-$version"
  if [ ! -f "$src/CMakeLists.txt" ]; then
    rm -rf "$src"; mkdir -p "$src"
    curl -fsSL "https://github.com/$repo/archive/refs/tags/$version.tar.gz" | tar xz -C "$src" --strip-components 1
  fi
  # shellcheck disable=SC2086
  cmake -S "$src" -B "$src/build" -DCMAKE_BUILD_TYPE=Release $PLATFORM \
    -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_BLAS=OFF $extra >/dev/null
  cmake --build "$src/build" --config Release --target "$target" -j "$JOBS" >/dev/null
  mkdir -p "$OUT"
  cp "$src/build/bin/$target" "$dest"
  echo "$version" > "$dest.version"
  echo "built $dest"
}

build_ace() {
  dest="$OUT/ace-server-$TRIPLE"
  if [ -x "$dest" ] && [ "$(cat "$dest.version" 2>/dev/null)" = "$ACE_COMMIT" ]; then
    echo "ace-server $ACE_COMMIT already built"
    return
  fi
  src="$CACHE/ace-server-$ACE_COMMIT"
  if [ ! -f "$src/CMakeLists.txt" ]; then
    rm -rf "$src"; mkdir -p "$CACHE"
    git clone --quiet https://github.com/ServeurpersoCom/acestep.cpp.git "$src"
    git -C "$src" checkout --quiet "$ACE_COMMIT"
    git -C "$src" submodule update --quiet --init --recursive
    # libc++ gates float from_chars behind macOS 26; the repo ships a portable parser, force it
    sed -i.bak 's/^#if defined(_LIBCPP_VERSION) && _LIBCPP_VERSION < 200000$/#if 1/' "$src/src/pipeline-synth-ops.cpp"
  fi
  # shellcheck disable=SC2086
  cmake -S "$src" -B "$src/build" -DCMAKE_BUILD_TYPE=Release $PLATFORM \
    -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF >/dev/null
  cmake --build "$src/build" --config Release --target ace-server -j "$JOBS" >/dev/null
  mkdir -p "$OUT"
  cp "$src/build/ace-server" "$dest"
  echo "$ACE_COMMIT" > "$dest.version"
  echo "built $dest"
}

build llama-server ggml-org/llama.cpp "$LLAMA_VERSION" llama-server \
  "-DLLAMA_CURL=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON"
build whisper-server ggml-org/whisper.cpp "$WHISPER_VERSION" whisper-server \
  "-DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_SERVER=ON"
build_ace
