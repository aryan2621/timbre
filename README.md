# VoiceClone Studio

A local, offline desktop app for voice cloning and text-to-speech. Give it 5–30 seconds of a voice, type a script, and it speaks in that voice. Nothing leaves your computer.

- **Clone from a recording or a file:** record with the microphone in the app, or import WAV, FLAC, OGG or MP3.
- **Plays while it renders:** long scripts are split into sentence-aware chunks and you hear the first one early.
- **Batch:** render many lines from `.txt`, `.csv` or `.srt` files into one folder.
- **History:** every render is kept; replay or export it as WAV.
- **Consent required:** a voice profile can't be created without confirming permission. Output carries a Perth watermark.
- **Sounds:** describe a sound effect or a piece of music, set its length (up to 47 s) and render it with [Stable Audio Open](https://huggingface.co/stabilityai/stable-audio-open-1.0).
- **Music:** [ACE-Step 1.5](https://huggingface.co/ACE-Step/Ace-Step1.5) makes songs up to four minutes, with optional lyrics. It runs on the bundled native `ace-server` (built by `desktop/scripts/build-native-servers.sh`), so nothing is installed besides the 5.6 GB of weights.
- **Engine:** [Chatterbox](https://github.com/resemble-ai/chatterbox) (MIT, 23 languages). Other engines can be added behind `app/engines/base.py`.

Stack: a Tauri 2 + React desktop shell talking to a local FastAPI backend in Python. The shell starts the backend itself, with a random per-launch token.

## Requirements

| | |
| --- | --- |
| Python | 3.12 (3.10–3.12 work) |
| Node / pnpm | Node 20+, pnpm |
| Rust | stable (`cargo`, `rustc`) |
| macOS / Linux | `ffmpeg` and `libsndfile` |
| Disk | about 8 GB (PyTorch plus the 6 GB Chatterbox weights) |
| GPU | optional: Apple Silicon (MPS) or NVIDIA (CUDA); CPU works but is slow |

## Setup

```bash
git clone https://github.com/aryan2621/voiceclone.git && cd voiceclone

python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'     # installs Chatterbox and PyTorch too

cd desktop && pnpm install
```

Sounds need two more packages. Chatterbox pins an older `diffusers`, so they go in as a second step (pip prints a version warning for Chatterbox, which can be ignored):

```bash
.venv/bin/pip install 'diffusers>=0.31' torchsde
```

Stable Audio Open is gated on Hugging Face: accept its licence on the model page, create your own read-only access token, and paste it on the **Models** page. The token is kept in the system keychain (a private file if none is available), is only sent to huggingface.co, and is never shown again. **Models** also checks your RAM, GPU and free disk and only offers downloads that fit this machine.

For NVIDIA GPUs install a CUDA build of PyTorch first (see pytorch.org), then the command above.

## Run

```bash
cd desktop
pnpm tauri dev
```

Then open **Models** and download the Chatterbox weights (once, about 6 GB). The first render also asks for microphone access if you record.

API only (no token, local callers accepted): `pnpm api` from `desktop/`.

## Build

```bash
cd desktop
pnpm build:app    # freezes the API with PyInstaller, then runs `tauri build`
```

macOS and Linux only. The PyInstaller build with PyTorch is large and may need extra `--hidden-import` flags. GitHub Actions builds it on every push to `main` (`.github/workflows/build-desktop.yml`).

## Test

```bash
.venv/bin/pytest -q
cd desktop && pnpm exec tsc --noEmit && pnpm lint
```

## Layout

| Path | What |
| --- | --- |
| `app/api/` | FastAPI routes, auth token, model downloads |
| `app/services/` | rendering jobs, batch, voice profiles |
| `app/engines/` | engine interface and Chatterbox |
| `app/audio/` | chunking, reference prep, stitching |
| `app/data/` | SQLite, model catalog |
| `desktop/src/` | React pages, hooks, UI |
| `desktop/src-tauri/` | Tauri shell |

## Tuning

- **Chunk size** (Settings → Audio & quality, default 200 characters): larger chunks sound more natural, smaller ones start faster. Rendering cost grows faster than linearly with chunk length.
- **Speed** other than 1.0 time-stretches each chunk (pitch is kept) and costs extra time; 1.0 skips it.

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md). Chatterbox is MIT licensed.
