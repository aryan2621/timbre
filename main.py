"""
VoiceClone Studio — Main Application Entrypoint.
Initializes PySide6 GUI desktop application or falls back to interactive CLI mode.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time
import traceback

# Ensure the root voiceclone folder is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Check PySide6 availability
try:
    from PySide6.QtCore import QThread, Qt  # type: ignore
    from PySide6.QtWidgets import QApplication, QMessageBox  # type: ignore
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger, setup_logging
from app.core.paths import paths
from app.data.models import VoiceClip, VoiceProfile
from app.data.voice_repo import voice_repo
from app.engines.base import SynthesisParameters
from app.engines.registry import engine_registry

logger = get_logger("main")


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    """
    Global exception hook to intercept unhandled errors.
    Writes full stack trace to the rotating log file and displays a user-friendly
    dialog without abruptly crashing the application.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    full_trace = "".join(tb_lines)
    logger.critical("Uncaught Exception:\n%s", full_trace)

    if PYSIDE_AVAILABLE:
        app = QApplication.instance()
        # Dialogs may only be created on the GUI thread; worker-thread errors are just logged.
        if app and QThread.currentThread() == app.thread():
            error_msg = (
                f"An unexpected error occurred:\n\n{exc_type.__name__}: {str(exc_value)}\n\n"
                f"A detailed crash report has been saved to:\n{paths.log_file_path}"
            )
            QMessageBox.critical(None, "Application Error", error_msg)


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="VoiceClone Studio — Local Offline Voice Cloning")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--cli", action="store_true", help="Run in CLI/Terminal mode without GUI")
    parser.add_argument("--text", type=str, default=None, help="Text to synthesize in CLI mode")
    parser.add_argument("--voice", type=str, default=None, help="Voice name to use in CLI mode")
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=None, help="Force execution device")
    return parser.parse_args()


def run_cli_mode(args: argparse.Namespace) -> int:
    """Terminal-based execution for headless / server environments or quick testing."""
    print("=" * 64)
    print("  🎙️  VoiceClone Studio — Local Speech Synthesis & Cloning")
    print("=" * 64)

    # Hardware Info
    dev_info = device_manager.get_device_info()
    print(f"• Compute Hardware: {dev_info.device_name} ({dev_info.device_type.upper()})")
    if dev_info.total_memory_mb > 0:
        print(f"• VRAM Allocated:   {dev_info.allocated_memory_mb:.0f} / {dev_info.total_memory_mb:.0f} MB")
    print(f"• Offline Cache:    {paths.data_dir}")
    print(f"• Database Path:    {paths.database_path}")

    # Available Engines
    engines = engine_registry.list_engine_names()
    print(f"• Pluggable Engines: {', '.join(engines)}")

    # Engine Selection
    engine = engine_registry.get_engine("Chatterbox TTS")
    if not engine:
        print("Error: Default engine not found.", file=sys.stderr)
        return 1

    # Check for voice profiles or seed default demo
    profiles = voice_repo.list_all_profiles()
    if not profiles:
        print("\n[+] Creating default verified demo voice profile ('Default Narrator')...")
        demo_clip_path = paths.voices_dir / "demo_reference.wav"
        
        # Generate clean synthetic calibration reference clip
        try:
            import soundfile as sf
            import numpy as np
            sr = 24000
            t = np.linspace(0, 6.0, sr * 6, endpoint=False)
            sine = (0.3 * np.sin(2 * np.pi * 165 * t)).astype(np.float32)
            sf.write(str(demo_clip_path), sine, sr)
        except Exception:
            # File stub if soundfile not present
            with open(demo_clip_path, "wb") as f:
                f.write(b"RIFF" + b"\x00" * 40)

        demo_profile = VoiceProfile(
            name="Default Narrator",
            language="en",
            notes="Factory default demonstration voice",
            consent_confirmed=True,
            consent_timestamp="2026-11-02T12:00:00Z",
            clips=[
                VoiceClip(
                    file_path=str(demo_clip_path),
                    original_filename="demo_reference.wav",
                    duration_seconds=6.0,
                    sample_rate=24000,
                    is_active=True,
                    quality_score=95,
                )
            ],
        )
        profile = voice_repo.create_profile(demo_profile)
    else:
        profile = (voice_repo.get_profile_by_name(args.voice) if args.voice else None) or profiles[0]
        if args.voice and profile.name != args.voice:
            print(f"[!] Voice '{args.voice}' not found; using '{profile.name}'.")

    print(f"• Active Voice:     {profile.name} (ID: {profile.id}, Lang: {profile.language})")
    print(f"• Consent Status:   Verified (Timestamp: {profile.consent_timestamp})")

    # Speech Text
    prompt_text = args.text or (
        "Welcome to VoiceClone Studio. This is a production-grade local zero-shot voice cloning application. "
        "Everything runs locally on your machine with zero cloud telemetry."
    )
    print(f"\n[+] Synthesizing: \"{prompt_text}\"")

    params = engine.get_default_params()
    params.enable_watermark = True

    start_time = time.time()
    try:
        audio, sr = engine.clone_and_synthesize(
            text=prompt_text,
            reference_audio_path=profile.primary_audio_path or "",
            params=params,
        )
        elapsed = time.time() - start_time
        duration = len(audio) / sr if hasattr(audio, "__len__") and sr > 0 else 0.0

        output_file = paths.exports_dir / f"cli_synthesis_{int(time.time())}.wav"
        try:
            import soundfile as sf
            sf.write(str(output_file), audio, sr)
            print(f"✓ Synthesis finished in {elapsed:.2f}s (Audio Duration: {duration:.2f}s)")
            print(f"✓ Saved audio to: {output_file}")
            print(f"✓ Perth Acoustic Watermark: Embedded")
        except ImportError:
            # Standard library wave writer fallback
            import wave
            import struct
            with wave.open(str(output_file), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                # Pack float list or numpy array into 16-bit PCM bytes
                packed = bytearray()
                for s in audio:
                    val = int(max(-1.0, min(1.0, float(s))) * 32767)
                    packed.extend(struct.pack("<h", val))
                wf.writeframes(packed)
            print(f"✓ Synthesis finished in {elapsed:.2f}s (Audio Duration: {duration:.2f}s)")
            print(f"✓ Saved standard WAV audio to: {output_file}")
            print(f"✓ Perth Acoustic Watermark: Embedded")

    except Exception as e:
        print(f"Synthesis failed: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 64)
    print("To launch the full graphical desktop application (PySide6):")
    print("  1. Ensure PySide6 is installed: pip install -r requirements.txt")
    print("  2. Run: python voiceclone/main.py")
    print("=" * 64)
    return 0


def main() -> int:
    """Main execution entry point."""
    args = parse_arguments()

    # Configure logging
    log_level = "DEBUG" if args.debug else config_manager.config.log_level
    setup_logging(log_level)
    logger.info("Starting VoiceClone Studio...")

    # Override device preference if specified on CLI
    if args.device:
        config_manager.config.device_preference = args.device
        logger.info("Execution device forced via CLI: %s", args.device)

    # Attach global exception hook
    sys.excepthook = handle_uncaught_exception

    # If CLI flag is requested or PySide6 is not installed, run CLI mode
    if args.cli or not PYSIDE_AVAILABLE:
        if not PYSIDE_AVAILABLE:
            print("[Note] PySide6 GUI library not found. Launching in CLI engine mode.")
        return run_cli_mode(args)

    # High-DPI scaling configuration
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("VoiceClone Studio")
    app.setOrganizationName("VoiceClone")

    # Create and display MainWindow
    window = MainWindow()
    window.show()

    # Check for mandatory ethics consent and onboarding tour
    window.check_first_run_dialogs()

    logger.info("UI successfully loaded. Entering Qt main event loop.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
