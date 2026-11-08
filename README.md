# Timbre

A local, offline desktop studio for voice cloning, text to speech, music, sound effects and voice agents. Everything runs on your Mac. Nothing you type or record leaves it.

## Install

1. Download the latest `.dmg` from [Releases](https://github.com/aryan2621/voiceclone/releases) and drag Timbre to Applications.
2. The app is not signed or notarized (that needs a paid Apple developer account), so macOS warns the first time. Right-click Timbre, choose **Open**, then **Open** again. If macOS says the app is damaged, run `xattr -dr com.apple.quarantine /Applications/Timbre.app`.
3. Open **Models** and download what you want to use. Models download on first use, so you need internet and free disk space once. After that Timbre works offline.

Apple Silicon only. You install nothing else: Python, the model servers and the audio tools are inside the app.

### What you need

- **Nothing**, for Chatterbox, ACE-Step, MusicGen, AudioLDM and all the agent models.
- **A free Hugging Face account**, only for the gated models (Stable Audio Open and Pocket TTS). Accept the licence on the model page, create a read-only token, and paste it on the **Models** page. The token is kept in the system keychain and only sent to huggingface.co. The Models page has a step-by-step dialog.
- **Microphone access**, only if you record a reference voice or talk to an agent.

## What it does

- **Studio:** one screen for speech, music and sound effects. Type or describe, press the arrow, and the settings drawer changes to match the mode and the model you picked.
- **Voice cloning:** record or import 5 to 30 seconds of a voice (WAV, FLAC, OGG, MP3) and it speaks your script in that voice. A voice profile needs a consent confirmation, and Chatterbox output carries a Perth watermark. Long scripts render in sentence-sized chunks and start playing after the first one.
- **Music:** songs with optional lyrics, tempo, key and more.
- **Sound effects:** describe a sound and render it.
- **Agents:** talk to a voice agent that listens (Whisper), thinks (a local language model) and answers in a cloned voice. Give each agent an icon and connect it to MCP servers (streamable HTTP) so it can use tools.
- **Batch and History:** render many lines from `.txt`, `.csv` or `.srt`; every render is kept for replay and WAV export.
- **Models:** one list per category with size, memory needs and a **Use** button that sets the default. It checks your RAM and disk and hides what won't fit.

### Models

| Category | Models | Account |
| --- | --- | --- |
| Voice cloning | Chatterbox (MIT, 23 languages), Pocket TTS (fast on CPU, English, CC BY 4.0) | Pocket TTS: Hugging Face |
| Sound effects | Stable Audio Open (up to 47 s), AudioLDM (up to 30 s, non-commercial) | Stable Audio: Hugging Face |
| Music | ACE-Step 1.5 (up to 10 min), MusicGen small (up to 40 s, non-commercial) | none |
| Voice agents | Qwen3 1.7B, 4B and 8B, Gemma 3 4B, Llama 3.1 8B; Whisper base and large v3 turbo | none |

Every setting a model supports is in the drawer: for example temperature, top-p, repetition penalty and speed for speech, steps, prompt strength and seed for sound, and tempo, key, time signature, vocal language, shift and solver for ACE-Step. Duration limits are set by what each model can do. Check each model's licence before commercial use.

Licences vary: Chatterbox is MIT, ACE-Step is Apache-2.0, Stable Audio Open is free under USD 1M revenue, and AudioLDM and MusicGen are non-commercial. See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Releases

Pushing to `main` builds the app in GitHub Actions and uploads the DMG as a workflow artifact. Pushing a version tag also publishes it on the Releases page:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

The workflow is `.github/workflows/build-desktop.yml`. It builds on macOS Apple Silicon only, because the music server is built for it.

## Build from source

You need Python 3.12, Node 20+ with pnpm, stable Rust, cmake and `libsndfile`.

```bash
git clone https://github.com/aryan2621/voiceclone.git && cd voiceclone

python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pip install 'diffusers>=0.31' torchsde      # Chatterbox pins an older diffusers, ignore its warning
.venv/bin/pip install --no-deps pocket-tts==4.0.1     # it asks for numpy 2 but runs on 1.26

cd desktop && pnpm install
sh scripts/build-native-servers.sh                    # llama.cpp, whisper.cpp and acestep.cpp servers

pnpm tauri dev                                        # run
pnpm build:app                                        # freeze the API and build the DMG
```

API only (no token, local callers accepted): `pnpm api` from `desktop/`.

## Test

```bash
.venv/bin/pytest -q
cd desktop && pnpm exec tsc --noEmit && pnpm lint
```

## Layout

| Path | What |
| --- | --- |
| `app/api/` | FastAPI routes, auth token, model downloads |
| `app/services/` | rendering jobs, agents, MCP client, batch, voice profiles |
| `app/engines/` | engine interface and one file per model |
| `app/runtimes/` | supervision of the native llama, whisper and ace servers |
| `app/data/` | SQLite, model catalog |
| `desktop/src/` | React pages, hooks, UI |
| `desktop/src-tauri/` | Tauri shell and app icon |

## License

MIT. See [LICENSE](LICENSE).
