"""
TTS Studio View: Interactive speech generation, hyperparameter tuning,
waveform player, real-time metrics, and audio export.
"""

from __future__ import annotations

import json
from pathlib import Path
import random
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
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLayout,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSlider,
        QSpinBox,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QWidget: pass

from app.audio.chunker import TextChunker
from app.audio.export import AudioExporter
from app.audio.player import AudioPlayer, PlaybackState
from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.history_repo import history_repo
from app.data.models import HistoryEntry, VoiceProfile
from app.data.voice_repo import voice_repo
from app.engines.base import SynthesisParameters, TTSEngine
from app.engines.registry import engine_registry
from app.ui.styles.icons import bind_icon
from app.ui.widgets.waveform import WaveformWidget
from app.workers.synth_worker import SynthesisWorker

logger = get_logger("studio_view")


class StudioView(QWidget):
    """Main Text-to-Speech synthesis studio interface."""

    activity = Signal()  # emitted when a job starts/finishes (keeps idle-unload from firing mid-use)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.player = AudioPlayer()
        self.worker: Optional[SynthesisWorker] = None
        self.active_audio: Optional[np.ndarray] = None
        self.active_sr: int = 24000
        self.last_preview_path: Optional[str] = None
        # Accumulates rendered chunks for the full-clip waveform / export
        # after streaming playback finishes.
        self._stream_chunks: list[np.ndarray] = []
        self._stream_sample_rate: int = 24000

        self._build_ui()
        self._refresh_voices()
        self._on_engine_changed()

        # Playback callbacks run on a PortAudio thread, so the GUI polls the player instead.
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(40)
        self._play_timer.timeout.connect(self._tick_playback)
        self._play_timer.start()

    def is_busy(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def shutdown(self) -> None:
        """Stops playback and waits for the synthesis thread (called on window close)."""
        self._play_timer.stop()
        self.player.stop()
        if self.is_busy():
            self.worker.cancel()
            self.worker.wait()

    def _tick_playback(self) -> None:
        self.waveform.update_position(self.player.current_position_seconds, self.player.duration_seconds)
        playing = self.player.state == PlaybackState.PLAYING
        if playing != self._playing_ui:
            self._set_play_button(playing)

    @staticmethod
    def _field(label: str, widget, value_label: Optional[QLabel] = None) -> QVBoxLayout:
        """Label above a control (value readout right-aligned on the label row when given)."""
        col = QVBoxLayout()
        col.setSpacing(4)
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setObjectName("mutedText")
        lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        row.addWidget(lbl)
        row.addStretch()
        if value_label is not None:
            row.addWidget(value_label)
        col.addLayout(row)
        if isinstance(widget, QLayout):
            col.addLayout(widget)
        else:
            col.addWidget(widget)
        return col

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 16)
        main_layout.setSpacing(20)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        # Selectors
        self.combo_voices = QComboBox()
        self.combo_voices.setToolTip("Select the reference voice profile ID.")
        self.combo_voices.currentIndexChanged.connect(self._on_voice_changed)
        self.combo_engine = QComboBox()
        self.combo_engine.setToolTip("Select TTS synthesis backend architecture.")
        self.combo_engine.addItems(engine_registry.list_engine_names())
        self.combo_engine.currentIndexChanged.connect(self._on_engine_changed)
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["en", "es", "fr", "de", "it", "pt", "ja", "zh"])

        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        top_bar.addLayout(self._field("Reference Voice", self.combo_voices), 3)
        top_bar.addLayout(self._field("TTS Engine", self.combo_engine), 3)
        top_bar.addLayout(self._field("Language Code", self.combo_lang), 1)
        left_layout.addLayout(top_bar)

        # Input text editor + live metrics
        self.txt_input = QPlainTextEdit()
        self.txt_input.setPlaceholderText("Type or paste synthesis input text")
        self.txt_input.setPlainText(
            "Welcome to VoiceClone Studio. This is a production-grade local zero-shot voice cloning application. "
            "Everything is processed securely on your computer without sending any data to the cloud."
        )
        self.txt_input.textChanged.connect(self._on_text_changed)
        left_layout.addLayout(self._field("Input Text", self.txt_input), 3)

        self.lbl_text_metrics = QLabel("Char Count: 0 | Word Count: 0 | Est. Duration: 0.0s")
        self.lbl_text_metrics.setObjectName("mutedText")
        self.lbl_text_metrics.setStyleSheet("font-size: 12px;")
        left_layout.addWidget(self.lbl_text_metrics)

        # Primary action
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.btn_generate = QPushButton("Run Synthesis")
        self.btn_generate.setObjectName("primaryButton")
        self.btn_generate.setToolTip("Run inference (Ctrl+Return / Cmd+Return)")
        bind_icon(self.btn_generate, "waveform", off="on_accent", size=18)
        self.btn_generate.clicked.connect(self.start_generation)
        action_layout.addWidget(self.btn_generate, 3)

        self.btn_cancel = QPushButton("Cancel Inference")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_generation)
        action_layout.addWidget(self.btn_cancel, 1)
        left_layout.addLayout(action_layout)

        # Progress + status share one quiet row
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("slimProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        left_layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        self.lbl_status = QLabel("Idle")
        self.lbl_status.setObjectName("mutedText")
        status_row.addWidget(self.lbl_status, 1)
        self.lbl_eta = QLabel("ETA: --")
        self.lbl_eta.setObjectName("mutedText")
        status_row.addWidget(self.lbl_eta)
        left_layout.addLayout(status_row)

        # Waveform + transport
        self.waveform = WaveformWidget(self)
        self.waveform.seek_requested.connect(self._on_seek_requested)
        left_layout.addWidget(self.waveform, 2)

        player_bar = QHBoxLayout()
        player_bar.setSpacing(8)
        self.btn_play = QPushButton("Playback")
        self.btn_play.setToolTip("Start / pause playback (Space)")
        self.btn_play.clicked.connect(self.toggle_playback)
        player_bar.addWidget(self.btn_play)
        self._set_play_button(False)

        self.btn_stop = QPushButton("Stop Playback")
        bind_icon(self.btn_stop, "stop", off="text", size=16)
        self.btn_stop.clicked.connect(self.stop_playback)
        player_bar.addWidget(self.btn_stop)

        player_bar.addSpacing(8)
        vol_icon = QLabel()
        bind_icon(vol_icon, "volume", off="text_muted", size=16)
        player_bar.addWidget(vol_icon)
        self.slider_volume = QSlider(Qt.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(100)
        self.slider_volume.setFixedWidth(110)
        self.slider_volume.setAccessibleName("Volume")
        self.slider_volume.valueChanged.connect(lambda v: self.player.set_volume(v / 100.0))
        player_bar.addWidget(self.slider_volume)
        player_bar.addStretch()

        self.btn_export = QPushButton("Export Waveform")
        self.btn_export.setToolTip("Save rendered output (Ctrl+S)")
        bind_icon(self.btn_export, "export", off="text", size=16)
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_audio)
        player_bar.addWidget(self.btn_export)
        left_layout.addLayout(player_bar)

        main_layout.addLayout(left_layout, 3)

        # Right column: tuning panel
        right_panel = QWidget()
        right_panel.setFixedWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self.lbl_exagg_val = QLabel("1.00x")
        self.lbl_exagg_val.setObjectName("mutedText")
        self.slider_exaggeration = QSlider(Qt.Horizontal)
        self.slider_exaggeration.setRange(20, 200)
        self.slider_exaggeration.setValue(100)
        self.slider_exaggeration.valueChanged.connect(
            lambda v: self.lbl_exagg_val.setText(f"{v / 100.0:.2f}x")
        )
        self.spin_cfg = QDoubleSpinBox()
        self.spin_cfg.setRange(1.0, 7.0)
        self.spin_cfg.setSingleStep(0.2)
        self.spin_cfg.setValue(2.0)
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.1, 1.5)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.65)

        grp_voice = QGroupBox("Prosody Parameters")
        v_layout = QVBoxLayout(grp_voice)
        v_layout.setSpacing(12)
        v_layout.addLayout(self._field("Exaggeration Scale", self.slider_exaggeration, self.lbl_exagg_val))
        v_layout.addLayout(self._field("CFG Weight (Guidance)", self.spin_cfg))
        v_layout.addLayout(self._field("Sampling Temperature", self.spin_temp))
        right_layout.addWidget(grp_voice)

        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setSingleStep(0.05)
        self.spin_speed.setValue(1.1)
        self.spin_speed.valueChanged.connect(self._on_text_changed)
        self.spin_pause = QSpinBox()
        self.spin_pause.setRange(0, 1500)
        self.spin_pause.setSingleStep(50)
        self.spin_pause.setSuffix(" ms")
        self.spin_pause.setValue(250)
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(-1, 99999999)
        self.spin_seed.setValue(-1)
        self.spin_seed.setEnabled(False)  # ignored while "Randomize" is on
        self.chk_random_seed = QCheckBox("Random Seed")
        self.chk_random_seed.setChecked(True)
        self.chk_random_seed.toggled.connect(self._on_random_seed_toggled)
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.spin_seed, 1)
        seed_row.addWidget(self.chk_random_seed)

        # Chunk-by-chunk streaming: hear each sentence as soon as it is rendered.
        self.chk_stream = QCheckBox("Stream sentence by sentence")
        self.chk_stream.setChecked(True)
        self.chk_stream.setToolTip(
            "Play each sentence the moment it is generated instead of waiting "
            "for the whole script to finish."
        )

        grp_delivery = QGroupBox("Delivery Parameters")
        d_layout = QVBoxLayout(grp_delivery)
        d_layout.setSpacing(12)
        d_layout.addLayout(self._field("Speed Multiplier", self.spin_speed))
        d_layout.addLayout(self._field("Inter-Sentence Silence", self.spin_pause))
        d_layout.addLayout(self._field("Deterministic Seed", seed_row))
        d_layout.addWidget(self.chk_stream)
        right_layout.addWidget(grp_delivery)

        # Watermark status
        wm_row = QHBoxLayout()
        wm_row.setContentsMargins(4, 0, 0, 0)
        wm_icon = QLabel()
        bind_icon(wm_icon, "lock", off="ok", size=14)
        wm_row.addWidget(wm_icon)
        self.lbl_watermark_notice = QLabel("Perth Watermark: Enabled")
        self.lbl_watermark_notice.setObjectName("okText")
        self.lbl_watermark_notice.setStyleSheet("font-size: 12px;")
        wm_row.addWidget(self.lbl_watermark_notice)
        wm_row.addStretch()
        right_layout.addLayout(wm_row)

        right_layout.addStretch()
        main_layout.addWidget(right_panel)

        self._on_text_changed()

    def _on_random_seed_toggled(self, randomize: bool) -> None:
        self.spin_seed.setEnabled(not randomize)
        self.spin_seed.setValue(-1 if randomize else random.randint(1000, 999999))

    def _set_play_button(self, playing: bool) -> None:
        self._playing_ui = playing
        self.btn_play.setText("Pause" if playing else "Play")
        bind_icon(self.btn_play, "pause" if playing else "play", off="text", size=16)

    def _refresh_voices(self) -> None:
        """Reloads available voice profiles into combo box, keeping the current selection."""
        wm_on = config_manager.config.enable_audio_watermark
        self.lbl_watermark_notice.setText(f"Perth Acoustic Watermark: {'enabled' if wm_on else 'disabled'}")
        previous = self.combo_voices.currentData()
        self.combo_voices.blockSignals(True)
        self.combo_voices.clear()
        profiles = voice_repo.list_all_profiles()
        for p in profiles:
            self.combo_voices.addItem(f"{p.name} ({p.language})", userData=p.id)

        if not profiles:
            self.combo_voices.addItem("No Voice Profiles Registered", userData=None)
        idx = self.combo_voices.findData(previous)
        if idx >= 0:
            self.combo_voices.setCurrentIndex(idx)
        self.combo_voices.blockSignals(False)
        if idx < 0:
            self._on_voice_changed()

    def _on_voice_changed(self) -> None:
        profile_id = self.combo_voices.currentData()
        if profile_id:
            profile = voice_repo.get_profile_by_id(profile_id)
            if profile and profile.language:
                idx = self.combo_lang.findText(profile.language)
                if idx >= 0:
                    self.combo_lang.setCurrentIndex(idx)

    def _on_engine_changed(self) -> None:
        engine_name = self.combo_engine.currentText()
        engine = engine_registry.get_engine(engine_name)
        if not engine:
            return

        # Show license alert if non-commercial (XTTS)
        if not engine.license_info.commercial_permitted:
            QMessageBox.warning(
                self,
                "Non-Commercial Engine License",
                engine.license_info.notice,
            )

        # Update language dropdown
        current_lang = self.combo_lang.currentText()
        self.combo_lang.clear()
        self.combo_lang.addItems(engine.supported_languages)
        idx = self.combo_lang.findText(current_lang)
        if idx >= 0:
            self.combo_lang.setCurrentIndex(idx)

    def _on_text_changed(self) -> None:
        text = self.txt_input.toPlainText()
        chars, words = TextChunker.count_metrics(text)
        speed = self.spin_speed.value()
        est_sec = TextChunker.estimate_duration_seconds(text, speed_multiplier=speed)
        self.lbl_text_metrics.setText(
            f"Char Count: {chars} | Word Count: {words} | Est. Duration: {est_sec:.1f}s"
        )

    def start_generation(self) -> None:
        """Launches background generation thread."""
        if self.is_busy():
            return
        profile_id = self.combo_voices.currentData()
        if not profile_id:
            QMessageBox.information(
                self,
                "No Voice Profile",
                "Select or create a reference voice profile in the Voices library first.",
            )
            return

        profile = voice_repo.get_profile_by_id(profile_id)
        if not profile or not profile.primary_audio_path:
            QMessageBox.warning(
                self,
                "No Reference Audio",
                "The selected voice profile has no valid reference audio clips.",
            )
            return

        text = self.txt_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty Input Text", "Please enter synthesis input text.")
            return

        engine_name = self.combo_engine.currentText()
        engine = engine_registry.get_engine(engine_name)
        if not engine:
            QMessageBox.critical(self, "Engine Not Registered", f"TTS engine '{engine_name}' is not registered.")
            return

        # Prepare parameters
        # Resolve a random seed here so history records the seed actually used.
        seed_val = random.randint(1, 99999999) if self.chk_random_seed.isChecked() else self.spin_seed.value()
        params = SynthesisParameters(
            temperature=self.spin_temp.value(),
            cfg_weight=self.spin_cfg.value(),
            exaggeration=self.slider_exaggeration.value() / 100.0,
            speed=self.spin_speed.value(),
            seed=seed_val,
            language=self.combo_lang.currentText(),
            enable_watermark=config_manager.config.enable_audio_watermark,
        )

        # Setup worker thread
        self.worker = SynthesisWorker(
            engine=engine,
            text=text,
            reference_audio_path=profile.primary_audio_path,
            params=params,
            sentence_pause_ms=self.spin_pause.value(),
            streaming=self.chk_stream.isChecked(),
        )

        self.worker.progress_updated.connect(self._on_worker_progress)
        self.worker.status_updated.connect(self._on_worker_status)
        # Chunk-by-chunk streaming: play each sentence as soon as it's rendered.
        self.worker.chunk_ready.connect(self._on_chunk_ready)
        self.worker.generation_finished.connect(
            lambda audio, sr, path, dur: self._on_worker_finished(audio, sr, path, dur, profile, engine, params, text)
        )
        self.worker.generation_failed.connect(self._on_worker_failed)
        # QThread.finished fires on every exit path, including cancel, so controls never stay locked.
        self.worker.finished.connect(self._reset_controls)

        self.btn_generate.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        self.activity.emit()
        self.worker.start()

    def _reset_controls(self) -> None:
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.activity.emit()

    def cancel_generation(self) -> None:
        if self.worker and self.worker.isRunning():
            self.lbl_status.setText("Cancelling Inference")
            self.worker.cancel()
            # Stop live streaming playback immediately.
            self.player.stop()
            self._stream_chunks = []

    def _on_worker_progress(self, current: int, total: int, percent: float, eta_str: str) -> None:
        self.progress_bar.setValue(int(percent))
        self.lbl_eta.setText(f"ETA: {eta_str}")

    def _on_worker_status(self, status_msg: str) -> None:
        self.lbl_status.setText(status_msg)

    def _on_chunk_ready(self, audio: np.ndarray, sample_rate: int, chunk_index: int, total_chunks: int) -> None:
        """Play each rendered chunk as soon as it arrives (chunk-by-chunk streaming).

        The first chunk starts stream mode and playback; subsequent chunks are
        appended to the live buffer so the user hears speech without waiting
        for the full text to finish.
        """
        if audio is None or len(audio) == 0:
            return

        # The first chunk opens the live output stream.
        if not self.player.is_streaming:
            self._stream_sample_rate = sample_rate
            if not self.player.start_stream_mode(sample_rate):
                logger.warning("Live playback unavailable; falling back to buffered playback.")

        self.player.append_chunk(audio, sample_rate)
        self._stream_chunks.append(np.asarray(audio, dtype=np.float32).copy())

        # Resume playback if the user paused the live stream.
        if self.player.state != PlaybackState.PLAYING:
            self.player.play()

        # Per-chunk progress indicator.
        percent = int(((chunk_index + 1) / max(1, total_chunks)) * 100.0)
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(f"Chunk {chunk_index + 1} of {total_chunks} — streaming playback")
        self.activity.emit()

    def _on_worker_finished(
        self,
        audio: np.ndarray,
        sample_rate: int,
        preview_path: str,
        elapsed_sec: float,
        profile: VoiceProfile,
        engine: TTSEngine,
        params: SynthesisParameters,
        text: str,
    ) -> None:
        # Build the full clip from streamed chunks for waveform, export and history.
        if self._stream_chunks:
            full_audio = np.concatenate(self._stream_chunks).astype(np.float32)
            full_sr = self._stream_sample_rate
        else:
            full_audio = audio
            full_sr = sample_rate

        self.active_audio = full_audio
        self.active_sr = full_sr
        self.last_preview_path = preview_path

        self.waveform.set_audio(full_audio, full_sr)
        if self.player.is_streaming:
            # Keep the live stream playing: loading the clip would cut off the
            # audio that has not been played yet. The clip is stored for replay.
            self.player.finish_stream()
            self.player.set_replay_buffer(full_audio)
        else:
            self.player.load_audio(full_audio, full_sr)

        # Reset streaming state for the next synthesis.
        self._stream_chunks = []
        self._stream_sample_rate = 24000

        self.btn_export.setEnabled(True)
        self.progress_bar.setValue(100)
        self.lbl_eta.setText("ETA: 0s")
        self.lbl_status.setText(f"Inference complete in {elapsed_sec:.2f}s!")

        # Log into SQLite history repository
        history_entry = HistoryEntry(
            voice_id=profile.id,
            voice_name=profile.name,
            engine_name=engine.name,
            prompt_text=text,
            parameters_json=json.dumps({
                "temperature": params.temperature,
                "cfg_weight": params.cfg_weight,
                "exaggeration": params.exaggeration,
                "speed": params.speed,
                "language": params.language,
            }),
            seed=params.seed,
            audio_path=preview_path,
            duration_seconds=len(full_audio) / full_sr,
            sample_rate=full_sr,
        )
        history_repo.add_entry(history_entry)

    def _on_worker_failed(self, error_message: str) -> None:
        self.lbl_status.setText("Inference Failed")
        QMessageBox.critical(self, "Inference Error", error_message)

    def toggle_playback(self) -> None:
        if self.player.state == PlaybackState.PLAYING:
            self.player.pause()
            self._set_play_button(False)
        else:
            if self.player.play():
                self._set_play_button(True)

    def stop_playback(self) -> None:
        self.player.stop()
        self._set_play_button(False)

    def _on_seek_requested(self, position_sec: float) -> None:
        self.player.seek(position_sec)

    def export_audio(self) -> None:
        """Presents file dialog and exports rendered audio."""
        if self.active_audio is None or len(self.active_audio) == 0:
            return

        default_name = f"voiceclone_export_{int(time.time())}.wav"
        default_dir = config_manager.get_exports_directory()
        suggested_path = default_dir / default_name

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Cloned Speech",
            str(suggested_path),
            "WAV Audio (*.wav);;MP3 Audio (*.mp3);;FLAC Audio (*.flac);;OGG Audio (*.ogg)",
        )
        if not file_path:
            return

        target_path = Path(file_path)
        fmt = target_path.suffix.lstrip(".").lower()
        if fmt not in AudioExporter.SUPPORTED_FORMATS:
            # No/unknown extension: use the format chosen in the dialog's filter.
            fmt = selected_filter.split("*.")[-1].rstrip(")").lower()
            target_path = target_path.with_name(target_path.name + f".{fmt}")

        try:
            success = AudioExporter.export(
                audio=self.active_audio,
                sample_rate=self.active_sr,
                output_path=target_path,
                format_str=fmt,
                bit_depth=config_manager.config.default_bit_depth,
            )
        except ValueError as e:
            logger.error("Export rejected: %s", e)
            success = False

        if success:
            QMessageBox.information(
                self,
                "Export Complete",
                f"Audio saved successfully to:\n{target_path}",
            )
        else:
            QMessageBox.critical(
                self,
                "Export Failed",
                "Could not export audio file. MP3/OGG need ffmpeg installed; check logs for details.",
            )
