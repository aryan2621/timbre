"""
Multi-step 'New Voice Profile' wizard:
Import/Record -> Preprocessing & Quality Analysis -> Consent -> Test Sentence -> Save.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Optional

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PySide6.QtCore import QTimer, Qt, Signal  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QCheckBox,
        QComboBox,
        QDialog,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QProgressBar,
        QPushButton,
        QStackedWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QDialog: pass
    class QWidget: pass

from app.audio.player import AudioPlayer
from app.audio.preprocess import AudioPreprocessor
from app.audio.quality import AudioQualityChecker
from app.audio.recorder import AudioRecorder
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.models import QualityReport, VoiceClip, VoiceProfile, utc_now_iso
from app.data.voice_repo import voice_repo
from app.engines.registry import engine_registry
from app.ui.styles.theme import status_color
from app.ui.widgets.waveform import WaveformWidget
from app.workers.synth_worker import SynthesisWorker

logger = get_logger("voice_wizard")


class VoiceWizardDialog(QDialog):
    """Wizard guiding the user through recording/importing, preprocessing, consent, and testing."""

    voice_created = Signal(int)  # Emits new profile ID

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Voice Profile")
        self.setMinimumSize(680, 560)
        self.setModal(True)

        self.recorder = AudioRecorder(sample_rate=24000)
        self.player_orig = AudioPlayer(sample_rate=24000)
        self.player_proc = AudioPlayer(sample_rate=24000)

        self.raw_audio: Optional[np.ndarray] = None
        self.raw_sr: int = 24000
        self.processed_audio: Optional[np.ndarray] = None
        self.quality_report: Optional[QualityReport] = None
        self.test_audio: Optional[np.ndarray] = None

        self._record_timer = QTimer(self)
        self._record_timer.setInterval(100)
        self._record_timer.timeout.connect(self._update_record_status)
        self._record_elapsed: float = 0.0

        # Audio callbacks run on PortAudio threads; widgets are only touched from this GUI timer.
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(40)
        self._play_timer.timeout.connect(self._tick_playback)
        self._play_timer.start()
        self._active_wave: Optional[WaveformWidget] = None
        self._test_worker: Optional[SynthesisWorker] = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # Wizard Header
        self.step_indicator = QLabel("Step 1 of 5: Profile Details", self)
        self.step_indicator.setObjectName("stepLabel")
        layout.addWidget(self.step_indicator)

        self.stack = QStackedWidget(self)
        self._build_step1_details()
        self._build_step2_source()
        self._build_step3_prepare()
        self._build_step4_consent()
        self._build_step5_test()
        layout.addWidget(self.stack)

        # Navigation Controls
        nav_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self._on_cancel)
        nav_layout.addWidget(self.btn_cancel)

        nav_layout.addStretch()

        self.btn_back = QPushButton("Back", self)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._prev_step)
        nav_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next", self)
        self.btn_next.setObjectName("primaryButton")
        self.btn_next.clicked.connect(self._next_step)
        nav_layout.addWidget(self.btn_next)

        layout.addLayout(nav_layout)

    # STEP 1: Details
    def _build_step1_details(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Eleanor Vance, Narrator Calm")
        form.addRow("Voice Name *:", self.txt_name)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["en", "es", "fr", "de", "it", "pt", "ja", "zh"])
        form.addRow("Primary Language:", self.combo_lang)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Optional notes on vocal style, tone, character")
        self.txt_notes.setMaximumHeight(80)
        form.addRow("Notes:", self.txt_notes)

        layout.addLayout(form)
        layout.addStretch()
        self.stack.addWidget(page)

    # STEP 2: Source Audio (Import or Record)
    def _build_step2_source(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        # Option A: Import File
        grp_import = QGroupBox("Option A: Import Clean Audio File")
        imp_layout = QHBoxLayout(grp_import)
        self.btn_import_file = QPushButton("Browse Audio File (.wav, .mp3, .flac, .ogg, .m4a)")
        self.btn_import_file.clicked.connect(self._import_audio_file)
        self.lbl_file_path = QLabel("No file selected.")
        self.lbl_file_path.setObjectName("mutedText")
        imp_layout.addWidget(self.btn_import_file)
        imp_layout.addWidget(self.lbl_file_path)
        layout.addWidget(grp_import)

        # Option B: Record via Microphone
        grp_rec = QGroupBox("Option B: Record Directly from Microphone")
        rec_layout = QVBoxLayout(grp_rec)

        # Phonetic Script
        rec_layout.addWidget(QLabel("Suggested Reference Script to Read Aloud (5–15 seconds):"))
        self.lbl_script = QLabel(f'"{self.recorder.get_suggested_script(0)}"')
        self.lbl_script.setWordWrap(True)
        self.lbl_script.setObjectName("scriptQuote")
        rec_layout.addWidget(self.lbl_script)

        # VU Level Meter & Timer
        meter_layout = QHBoxLayout()
        self.vu_meter = QProgressBar()
        self.vu_meter.setRange(-60, 0)
        self.vu_meter.setValue(-60)
        self.vu_meter.setFormat("Level: %v dBFS")
        self.lbl_rec_timer = QLabel("00:00")
        self.lbl_rec_timer.setObjectName("errText")
        meter_layout.addWidget(self.vu_meter)
        meter_layout.addWidget(self.lbl_rec_timer)
        rec_layout.addLayout(meter_layout)

        # Record / Stop Buttons
        rec_btns = QHBoxLayout()
        self.btn_record = QPushButton("Start Recording")
        self.btn_record.clicked.connect(self._toggle_recording)
        rec_btns.addWidget(self.btn_record)
        rec_layout.addLayout(rec_btns)

        layout.addWidget(grp_rec)
        layout.addStretch()
        self.stack.addWidget(page)

    # STEP 3: Preprocessing & Quality Check
    def _build_step3_prepare(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        # Prep Options
        grp_opts = QGroupBox("Preprocessing Options")
        opts_layout = QHBoxLayout(grp_opts)
        self.chk_denoise = QCheckBox("Noise Reduction (Spectral Gating)")
        self.chk_denoise.setChecked(True)
        self.chk_vad = QCheckBox("Trim Silence (VAD)")
        self.chk_vad.setChecked(True)
        self.chk_norm = QCheckBox("Normalize Loudness (-23 LUFS)")
        self.chk_norm.setChecked(True)
        for chk in (self.chk_denoise, self.chk_vad, self.chk_norm):
            chk.toggled.connect(self._process_and_evaluate_audio)
        opts_layout.addWidget(self.chk_denoise)
        opts_layout.addWidget(self.chk_vad)
        opts_layout.addWidget(self.chk_norm)
        layout.addWidget(grp_opts)

        # Waveform & Playback of Processed Audio
        layout.addWidget(QLabel("Processed Reference Waveform:"))
        self.wave_widget = WaveformWidget(self)
        self.wave_widget.seek_requested.connect(self.player_proc.seek)
        layout.addWidget(self.wave_widget)

        play_layout = QHBoxLayout()
        self.btn_play_proc = QPushButton("Play Processed")
        self.btn_play_proc.clicked.connect(self._toggle_play_processed)
        play_layout.addWidget(self.btn_play_proc)
        play_layout.addStretch()
        layout.addLayout(play_layout)

        # Quality Report Box
        self.grp_quality = QGroupBox("Acoustic Quality Analysis")
        q_layout = QVBoxLayout(self.grp_quality)
        self.lbl_quality_summary = QLabel("Run quality analysis on audio")
        self.lbl_quality_summary.setWordWrap(True)
        q_layout.addWidget(self.lbl_quality_summary)
        layout.addWidget(self.grp_quality)

        self.stack.addWidget(page)

    # STEP 4: Mandatory Consent
    def _build_step4_consent(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(14)

        title = QLabel("Speaker Consent & Authorization Required")
        title.setObjectName("errText")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        desc = QLabel(
            "To uphold safety standards and avoid non-consensual voice generation, "
            "you must legally confirm that you have explicit permission from the speaker.\n\n"
            "This timestamped verification will be permanently attached to this voice profile."
        )
        desc.setWordWrap(True)
        desc.setObjectName("mutedText")
        desc.setStyleSheet("line-height: 1.4;")
        layout.addWidget(desc)

        self.chk_profile_consent = QCheckBox(
            "I explicitly own this voice or have received verifiable permission from the speaker "
            "to synthesize speech in their likeness.",
            self,
        )
        self.chk_profile_consent.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.chk_profile_consent.toggled.connect(self._on_consent_checked)
        layout.addWidget(self.chk_profile_consent)

        layout.addStretch()
        self.stack.addWidget(page)

    # STEP 5: Test Sentence & Finalize
    def _build_step5_test(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel("Test Cloned Voice (Optional Synthesis Verification):"))
        self.txt_test_sentence = QLineEdit("Hello, this is a test of my newly cloned voice in VoiceClone Studio.")
        layout.addWidget(self.txt_test_sentence)

        test_btns = QHBoxLayout()
        self.btn_run_test = QPushButton("Synthesize Test Sample")
        self.btn_run_test.clicked.connect(self._run_test_synthesis)
        self.lbl_test_status = QLabel("")
        test_btns.addWidget(self.btn_run_test)
        test_btns.addWidget(self.lbl_test_status)
        test_btns.addStretch()
        layout.addLayout(test_btns)

        self.test_wave_widget = WaveformWidget(self)
        self.test_wave_widget.seek_requested.connect(self.player_proc.seek)
        layout.addWidget(self.test_wave_widget)

        self.btn_play_test = QPushButton("Play Test Audio")
        self.btn_play_test.setEnabled(False)
        self.btn_play_test.clicked.connect(self._play_test_audio)
        layout.addWidget(self.btn_play_test)

        layout.addStretch()
        self.stack.addWidget(page)

    # Logic & Navigation
    def _next_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            name = self.txt_name.text().strip()
            if not name:
                self.txt_name.setFocus()
                return
            if voice_repo.get_profile_by_name(name):
                self.txt_name.setFocus()
                self.step_indicator.setText("A voice with that name already exists. Choose another name.")
                return
            self._go_to_step(1)

        elif idx == 1:
            if self.raw_audio is None or len(self.raw_audio) == 0:
                self.lbl_file_path.setText("Please import an audio file or record from the microphone first.")
                self.lbl_file_path.setStyleSheet(f"color: {status_color('err')};")
                return
            self._process_and_evaluate_audio()
            self._go_to_step(2)

        elif idx == 2:
            self._go_to_step(3)

        elif idx == 3:
            if not self.chk_profile_consent.isChecked():
                return
            self._go_to_step(4)

        elif idx == 4:
            self._save_profile_and_finish()

    def _prev_step(self) -> None:
        idx = self.stack.currentIndex()
        if idx > 0:
            self._go_to_step(idx - 1)

    def _go_to_step(self, step_idx: int) -> None:
        self.stack.setCurrentIndex(step_idx)
        titles = [
            "Step 1 of 5: Profile Details",
            "Step 2 of 5: Source Audio",
            "Step 3 of 5: Preprocessing & Quality Check",
            "Step 4 of 5: Consent & Authorization",
            "Step 5 of 5: Test & Finalize",
        ]
        self.step_indicator.setText(titles[step_idx])
        self.btn_back.setEnabled(step_idx > 0)
        self.btn_next.setText("Save Profile" if step_idx == 4 else "Next")
        if step_idx == 3:
            self.btn_next.setEnabled(self.chk_profile_consent.isChecked())
        else:
            self.btn_next.setEnabled(True)

    def _on_consent_checked(self, checked: bool) -> None:
        if self.stack.currentIndex() == 3:
            self.btn_next.setEnabled(checked)

    def _import_audio_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Speaker Audio Recording",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a);;All Files (*)",
        )
        if not file_path:
            return

        try:
            import soundfile as sf
            data, sr = sf.read(file_path, dtype="float32")
            self.raw_audio = data
            self.raw_sr = sr
            self.lbl_file_path.setText(Path(file_path).name)
            self.lbl_file_path.setStyleSheet(f"color: {status_color('ok')};")
        except Exception as e:
            logger.error("Failed to import audio: %s", e)
            self.lbl_file_path.setText(f"Error: {e}")
            self.lbl_file_path.setStyleSheet(f"color: {status_color('err')};")

    def _toggle_recording(self) -> None:
        if not self.recorder.is_recording:
            # Start
            success = self.recorder.start_recording()
            if success:
                self.btn_record.setText("Stop Recording")
                self.btn_record.setStyleSheet(f"color: {status_color('err')}; border-color: {status_color('err')};")
                self._record_elapsed = 0.0
                self._record_timer.start()
        else:
            # Stop
            self._record_timer.stop()
            audio = self.recorder.stop_recording()
            self.btn_record.setText("Record Again")
            self.btn_record.setStyleSheet("")
            self.vu_meter.setValue(-60)
            if audio is not None and len(audio) > 0:
                self.raw_audio = audio
                self.raw_sr = self.recorder.sample_rate
                duration = len(audio) / self.raw_sr
                self.lbl_file_path.setText(f"Captured {duration:.1f}s via Microphone")
                self.lbl_file_path.setStyleSheet(f"color: {status_color('ok')};")

    def _update_record_status(self) -> None:
        self.vu_meter.setValue(max(-60, int(self.recorder.last_dbfs)))
        self._record_elapsed += 0.1
        sec = int(self._record_elapsed)
        self.lbl_rec_timer.setText(f"{sec // 60:02d}:{sec % 60:02d}")

    def _process_and_evaluate_audio(self) -> None:
        if self.raw_audio is None:
            return

        self.processed_audio, sr = AudioPreprocessor.process_reference_audio(
            self.raw_audio,
            orig_sr=self.raw_sr,
            target_sr=24000,
            apply_denoise=self.chk_denoise.isChecked(),
            apply_vad=self.chk_vad.isChecked(),
            apply_normalize=self.chk_norm.isChecked(),
        )

        self.wave_widget.set_audio(self.processed_audio, sr)
        self.player_proc.load_audio(self.processed_audio, sr)
        self._active_wave = self.wave_widget

        # Quality analysis
        self.quality_report = AudioQualityChecker.analyze(self.processed_audio, sr)
        color = status_color("ok" if self.quality_report.score >= 70 else ("warn" if self.quality_report.score >= 50 else "err"))
        warnings_html = "".join(f"<li>{w}</li>" for w in self.quality_report.warnings)

        self.lbl_quality_summary.setText(
            f"<b>Quality Score:</b> <span style='color:{color}; font-size:16px;'>{self.quality_report.score}/100</span><br>"
            f"<b>Duration:</b> {self.quality_report.duration_seconds}s | "
            f"<b>Estimated SNR:</b> {self.quality_report.snr_db} dB | "
            f"<b>Clipping:</b> {self.quality_report.clipping_ratio * 100:.2f}%<br>"
            f"<b>Warnings / Recommendations:</b><ul>{warnings_html if warnings_html else '<li>Clean reference audio. Ideal for voice cloning!</li>'}</ul>"
        )

    def _tick_playback(self) -> None:
        playing = self.player_proc.state.value == "playing"
        if self._active_wave is not None:
            self._active_wave.update_position(
                self.player_proc.current_position_seconds, self.player_proc.duration_seconds
            )
        if not playing and self.player_proc.state.value == "stopped":
            self.btn_play_proc.setText("Play Processed")

    def _toggle_play_processed(self) -> None:
        if self.player_proc.state.value == "playing":
            self.player_proc.pause()
            self.btn_play_proc.setText("Play Processed")
        else:
            self.player_proc.play()
            self.btn_play_proc.setText("Pause")

    def _run_test_synthesis(self) -> None:
        if self._test_worker is not None and self._test_worker.isRunning():
            return
        engine = engine_registry.get_engine("Chatterbox TTS")
        if not engine:
            self.lbl_test_status.setText("Engine not available.")
            return

        # Save temporary reference clip
        temp_ref = paths.temp_dir / "wizard_test_ref.wav"
        import soundfile as sf
        sf.write(str(temp_ref), self.processed_audio, 24000)

        self.lbl_test_status.setText("Synthesizing")
        self._set_test_busy(True)
        text = self.txt_test_sentence.text().strip()
        worker = SynthesisWorker(
            engine, text, temp_ref, engine.get_default_params(), parent=self, preview_dir=paths.temp_dir
        )
        worker.generation_finished.connect(self._on_test_finished)
        worker.generation_failed.connect(lambda msg: self.lbl_test_status.setText(msg))
        worker.finished.connect(lambda: self._set_test_busy(False))
        self._test_worker = worker
        worker.start()

    def _set_test_busy(self, busy: bool) -> None:
        for btn in (self.btn_run_test, self.btn_next, self.btn_back):
            btn.setEnabled(not busy)

    def _on_test_finished(self, audio, sr: int, _path: str, _elapsed: float) -> None:
        self.test_audio = audio
        self.test_sr = sr
        self.test_wave_widget.set_audio(audio, sr)
        self.btn_play_test.setEnabled(True)
        self.lbl_test_status.setText("Ready!")

    def _play_test_audio(self) -> None:
        if self.test_audio is not None:
            self.player_proc.load_audio(self.test_audio, getattr(self, "test_sr", 24000))
            self._active_wave = self.test_wave_widget
            self.player_proc.play()

    def _save_profile_and_finish(self) -> None:
        name = self.txt_name.text().strip()
        lang = self.combo_lang.currentText()
        notes = self.txt_notes.toPlainText().strip()

        # Save processed reference clip into app-data voices folder
        safe_name = "".join(c for c in name if c.isalnum() or c in ("-", "_")).lower()
        clip_filename = f"{safe_name}_{int(time.time())}.wav"
        dest_clip_path = paths.voices_dir / clip_filename

        import soundfile as sf
        sf.write(str(dest_clip_path), self.processed_audio, 24000)

        duration = len(self.processed_audio) / 24000.0
        score = self.quality_report.score if self.quality_report else 80

        clip = VoiceClip(
            file_path=str(dest_clip_path),
            original_filename=self.lbl_file_path.text(),
            duration_seconds=duration,
            sample_rate=24000,
            is_active=True,
            quality_score=score,
        )

        profile = VoiceProfile(
            name=name,
            language=lang,
            notes=notes,
            consent_confirmed=True,
            consent_timestamp=utc_now_iso(),
            clips=[clip],
        )

        try:
            created = voice_repo.create_profile(profile)
        except sqlite3.IntegrityError:
            dest_clip_path.unlink(missing_ok=True)
            self.step_indicator.setText("A voice with that name already exists. Go back and choose another name.")
            return
        if created.id:
            self.voice_created.emit(created.id)

        self.accept()

    def _on_cancel(self) -> None:
        self.reject()

    def done(self, result: int) -> None:
        """Single cleanup path for Save, Cancel, Esc and the window close button."""
        self._play_timer.stop()
        self._record_timer.stop()
        self.player_proc.stop()
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        if self._test_worker is not None and self._test_worker.isRunning():
            self._test_worker.cancel()
            self._test_worker.wait()
        super().done(result)
