# VoiceClone Studio 🎙️

**A 100% Local, Offline Desktop Application for Zero-Shot Voice Cloning & Text-to-Speech.**

Runs entirely on your local machine: a Tauri + React desktop app talking to a local Python (PyTorch) engine. No cloud APIs, no subscriptions, zero telemetry, and complete privacy.

---

## Key Features

- **Zero-Shot Voice Cloning:** Clone any voice using 5 to 30 seconds of clean reference audio.
- **Sentence-Aware Rendering:** Scripts are split into sentence-aware chunks and rendered with crossfades and natural pauses, so the result is one continuous waveform instead of a robotic concatenation. The render runs in a background job and the UI reports progress, ETA and the waveform while it runs.
- **Offline & Private:** All inference runs on your local CPU or GPU. No network access required once models are cached.
- **Pluggable Engine Architecture:** Chatterbox is the one engine shipped, chosen as the best local, commercial-friendly option. Other engines can be added behind the `TTSEngine` interface.
  - **Chatterbox TTS (Default):** Permissive MIT license, embedded Perth acoustic watermark. Multilingual (23 languages including Hindi) via Chatterbox MultilingualTTS — auto-selected for non-English synthesis.
- **Reference Voice Prep & Quality Diagnostics:** Automated mono conversion, resampling, spectral noise reduction, VAD silence trimming, -23 LUFS loudness normalization, and SNR/clipping health checks.
- **Interactive Audio Studio:** Playback starts while the render is still running, waveform scrubbing, speech rate, CFG weight and emotion controls, and WAV export.
- **Batch Processing:** Synthesize hundreds of dialogue lines from `.txt`, `.csv`, or `.srt` subtitle files with queue controls and retry logic.
- **Record or Import a Reference:** Record from the microphone inside the New voice dialog (up to 30 s) or import a WAV, FLAC, OGG or MP3 file.
- **Ethics & Consent Guardrails:** A consent confirmation is required, and enforced by the API, before a voice profile is created; Perth audio watermarking.

---

## Hardware Requirements

| Component | Minimum (CPU Mode) | Recommended (GPU Accelerated) | High-Performance (Studio Multi-Engine) |
| :--- | :--- | :--- | :--- |
| **OS** | Windows 10/11, macOS 12+, Linux (Ubuntu 22.04+) | Windows 10/11, macOS 13+, Ubuntu 22.04+ | Windows 11, macOS 14+, Linux |
| **Processor** | 4-Core Intel/AMD x86_64 or Apple M1 | 8-Core Intel/AMD Ryzen or Apple M2/M3 | 12+ Core Modern CPU |
| **GPU** | None (CPU Fallback) | NVIDIA RTX 3060+ (CUDA 12) or Apple Silicon (MPS) | NVIDIA RTX 4070/4080/4090 or Apple M3 Max |
| **VRAM** | N/A | **6 GB VRAM** (Chatterbox) | **12+ GB VRAM** |
| **System RAM** | 8 GB | 16 GB | 32 GB |
| **Disk Storage** | 2 GB free (Application + Default Model) | 10 GB free SSD | 25 GB free NVMe SSD |

---

## Installation & Setup

### 1. Prerequisites
- **Python 3.11** (Recommended. Compatible with 3.10–3.12).
- **FFmpeg** (Required for MP3/OGG encoding and compressed audio import):
  - **macOS:** `brew install ffmpeg`
  - **Windows:** `winget install Gyan.FFmpeg` or `choco install ffmpeg`
  - **Linux (Ubuntu/Debian):** `sudo apt update && sudo apt install -y ffmpeg libsndfile1 portaudio19-dev`

### 2. Clone & Virtual Environment Setup
```bash
git clone https://github.com/your-repo/voiceclone.git
cd voiceclone

# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
# macOS / Linux:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
```

### 3. Install PyTorch with Hardware Acceleration
Choose the command matching your operating system and GPU:

- **NVIDIA GPU (CUDA 12.1 - Windows / Linux):**
  ```bash
  pip install torch==2.3.0+cu121 torchaudio==2.3.0+cu121 --index-url https://download.pytorch.org/whl/cu121
  ```
- **macOS (Apple Silicon M1/M2/M3 with MPS):**
  ```bash
  pip install torch==2.3.0 torchaudio==2.3.0
  ```
- **CPU Only (Windows / Linux):**
  ```bash
  pip install torch==2.3.0+cpu torchaudio==2.3.0+cpu --index-url https://download.pytorch.org/whl/cpu
  ```

### 4. Install Application Dependencies
```bash
pip install -r voiceclone/requirements.txt
```

---

## Running the Application

Launch the desktop UI:
```bash
python voiceclone/main.py
```

### Optional Command-Line Arguments:
- `--debug`: Enable verbose console and log diagnostics.
- `--device {auto,cuda,mps,cpu}`: Force a specific execution backend.

**Note:** in this checkout the entry point is `main.py` at the project root, so run `python main.py`.

---

## Desktop Frontend (Tauri + React)

The desktop app lives in `desktop/`: a Tauri 2 window with React, TypeScript,
Tailwind CSS v4 and shadcn/ui. The Python API in `app/` runs every engine,
audio and SQLite operation. The Tauri shell starts the API itself and stops it
on exit; each launch uses a random token (`VOICECLONE_API_TOKEN`) so only the
app can call it.

### Requirements
- Node.js 20+ and pnpm
- Rust toolchain (`cargo`, `rustc`) for the Tauri shell
- The Python environment from the setup steps above, in `.venv` at the repo root

### Run
```bash
cd desktop
pnpm install
pnpm tauri dev      # starts the Tauri window and the Python API
```

To run the API on its own (no token, any local caller is accepted):
```bash
pnpm api            # FastAPI on 127.0.0.1:8756 (from desktop/)
```

In the desktop app an unreachable engine shows "Engine offline" and empty
lists. Only a plain browser session (`pnpm dev`) falls back to demo data.

### Layout
| Path | Purpose |
| --- | --- |
| `desktop/src/pages/` | Studio, Voices, Batch, History, Models, Settings |
| `desktop/src/lib/api.ts` | Typed HTTP client for the sidecar |
| `desktop/src/components/waveform.tsx` | Canvas waveform with seek + playhead |
| `app/api/server.py` | FastAPI transport: voices, history, jobs, settings, models |
| `app/data/model_catalog.py` | Shared model metadata (downloads, sizes, SHA-256) |

### Rendering architecture

| Layer | Path | Role |
| --- | --- | --- |
| Text chunking | `app/audio/chunker.py` | Splits the script into sentence-aware chunks |
| Rendering | `app/services/synthesis_service.py` | Renders each chunk, post-processes on a second thread, stitches with crossfades |
| Stitching | `app/audio/stitch.py` | `prepare_chunk` and `stitch_chunks` |
| Desktop transport | `app/api/server.py` | `POST /api/synthesize` starts a job, `GET /api/jobs/{id}` reports its progress |
| Desktop playback | `desktop/src/hooks/use-studio.ts` | Plays finished chunks while rendering (`/api/jobs/{id}/chunks/{n}`), then the final file |

A render runs in a background thread on the backend, so the API stays
responsive. The desktop client polls the job status once per second, which
gives it the progress, the ETA and the waveform peaks while the render is
running. When the job is done the rendered file is served from
`/api/history/{id}/audio` and the UI plays it with the regular media element.

Chunks are prepared with the same sentence pause and edge fades used by the
final stitch (`app.audio.stitch.prepare_chunk`), so the rendered file is one
continuous waveform. Every render is persisted to History, so it can be
replayed or exported later.

### Chunk size and speed

Generation cost grows roughly **quadratically** with the length of a chunk, so
rendering a long script in many small chunks is significantly faster than
rendering it in a few big ones. Measured on an Apple Silicon (MPS) machine
with Chatterbox, for the same script:

| Characters per chunk | Chunks | Total render | Audio | Real-time factor |
| --- | --- | --- | --- | --- |
| 220 | 2 | 62.3 s | 12.4 s | 5.04x |
| **110** | **5** | **31.9 s** | **14.5 s** | **2.20x** |
| 55 | 11 | 67.2 s | 27.7 s | 2.42x |

That benchmark favoured small chunks. The default is now **200 characters**,
because play-while-rendering hides the wait for the first sentence and larger
chunks sound more natural. Tune it in **Settings → Audio & quality → Maximum
characters per chunk** (or `max_chars_per_chunk` in `config.json`).

The **Speed Multiplier**: Chatterbox has no native speed control, so at a
speed other than 1.0 its chunks are time-stretched with a phase vocoder
(librosa) on a second thread while the next chunk renders, which keeps the
pitch intact. The default speed is 1.0, which skips it.

### Production build
```bash
cd desktop
pnpm build:app      # freezes the API with PyInstaller, then runs `tauri build`
```
`pnpm build:sidecar` alone builds just the frozen API into
`src-tauri/binaries/` (macOS and Linux; the PyInstaller build with PyTorch is
large and may need extra `--hidden-import` flags for your engines).

---

## First-Use Walkthrough

1. **Create a Voice Profile:**
   - Navigate to the **Voices** tab on the left sidebar.
   - Click **New voice** (or press the shortcut shown in the command palette).
   - Enter a name (e.g., "Elena Storyteller").
   - **Option A:** Click *Choose file* to import a clean recording (5–30 s).
   - **Option B:** Click *Record with microphone*, speak, then *Stop*. Allow microphone access when macOS asks.
   - Tick the consent checkbox and click **Create profile**. The quality score appears on the voice card.
2. **Generate Speech in Studio:**
   - Switch to the **Studio** tab.
   - Select your newly created voice from the top dropdown.
   - Enter your text in the speech editor.
   - Adjust the **Emotion / Exaggeration** or **Speaking Rate** sliders if desired.
   - Click **Synthesize Speech (Ctrl+Enter)**.
   - View generation progress, ETA, and preview the resulting audio on the interactive waveform scrubber.
   - Export the render as WAV from the Studio or History page.

---

## Running Unit Tests

Run the test suite with `pytest`:
```bash
pytest tests -v
```
Or run using standard Python `unittest`:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

---

## License

This software application is released under the **MIT License**. See [LICENSE](LICENSE) and [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for complete details.

