"""
Batch Processing View: Bulk synthesis queue from .txt, .csv, and .srt subtitle files.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

try:
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QComboBox,
        QFileDialog,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QWidget: pass

from app.ui.styles.icons import bind_icon
from app.ui.styles.theme import configure_table, status_brush
from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.models import BatchJob
from app.data.voice_repo import voice_repo
from app.engines.base import SynthesisParameters
from app.engines.registry import engine_registry
from app.workers.batch_worker import BatchWorker

logger = get_logger("batch_view")


class BatchView(QWidget):
    """Executes multi-line bulk TTS generation with queue management."""

    activity = Signal()  # emitted when a batch starts/finishes (keeps idle-unload from firing mid-run)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.jobs: List[BatchJob] = []
        self.worker: Optional[BatchWorker] = None
        self._build_ui()
        self._refresh_voices()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header & File Picker
        top_bar = QHBoxLayout()
        header_lbl = QLabel("Batch Synthesis Studio")
        header_lbl.setObjectName("pageHeader")
        top_bar.addWidget(header_lbl)

        top_bar.addStretch()

        self.btn_import = QPushButton("Import script")
        self.btn_import.setToolTip("Import a .txt, .csv or .srt script")
        bind_icon(self.btn_import, "upload", off="text", size=16)
        self.btn_import.clicked.connect(self._import_batch_file)
        top_bar.addWidget(self.btn_import)

        layout.addLayout(top_bar)

        # Config Row: Voice, Engine, Output Folder
        cfg_bar = QHBoxLayout()
        cfg_bar.addWidget(QLabel("Voice:"))
        self.combo_voices = QComboBox()
        cfg_bar.addWidget(self.combo_voices, 2)

        cfg_bar.addWidget(QLabel("Engine:"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(engine_registry.list_engine_names())
        cfg_bar.addWidget(self.combo_engine, 2)

        self.btn_dest = QPushButton("Output folder")
        bind_icon(self.btn_dest, "folder", off="text", size=16)
        self.btn_dest.clicked.connect(self._choose_output_dir)
        cfg_bar.addWidget(self.btn_dest, 2)

        self.lbl_dest = QLabel()
        self.lbl_dest.setObjectName("mutedText")
        self.lbl_dest.setStyleSheet("font-size: 12px;")
        self.lbl_dest.setMinimumWidth(0)
        cfg_bar.addWidget(self.lbl_dest, 3)
        self._set_out_dir(config_manager.get_exports_directory())

        layout.addLayout(cfg_bar)

        # Queue Table
        self.table = QTableWidget(self)
        configure_table(self.table)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["#", "Target Filename", "Prompt Text", "Status", "Duration"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        self.lbl_empty = QLabel("Import a .txt, .csv or .srt script to build the queue.")
        self.lbl_empty.setObjectName("mutedText")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_empty)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.btn_start = QPushButton("Start batch")
        self.btn_start.setObjectName("primaryButton")
        bind_icon(self.btn_start, "play", off="on_accent", size=16)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start_batch)
        bottom_bar.addWidget(self.btn_start)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_batch)
        bottom_bar.addWidget(self.btn_stop)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom_bar.addWidget(self.progress_bar, 2)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setObjectName("mutedText")
        bottom_bar.addWidget(self.lbl_status)

        layout.addLayout(bottom_bar)

    def is_busy(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def shutdown(self) -> None:
        """Cancels the queue and waits for the thread (called on window close)."""
        if self.is_busy():
            self.worker.cancel()
            self.worker.wait()

    def _set_running(self, running: bool) -> None:
        for w in (self.btn_import, self.btn_dest, self.combo_voices, self.combo_engine):
            w.setEnabled(not running)
        self.btn_start.setEnabled(not running and bool(self.jobs) and self.combo_voices.currentData() is not None)
        self.btn_stop.setEnabled(running)

    def _refresh_voices(self) -> None:
        previous = self.combo_voices.currentData()
        self.combo_voices.clear()
        profiles = voice_repo.list_all_profiles()
        for p in profiles:
            self.combo_voices.addItem(p.name, userData=p.id)
        idx = self.combo_voices.findData(previous)
        if idx >= 0:
            self.combo_voices.setCurrentIndex(idx)
        self.btn_start.setEnabled(bool(self.jobs) and bool(profiles) and not self.is_busy())

    def _choose_output_dir(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Batch Output Directory")
        if dir_path:
            self._set_out_dir(dir_path)

    def _set_out_dir(self, directory) -> None:
        """Stores the real path; the label shows it elided so a long path can't widen the window."""
        self._out_dir = Path(directory)
        full = str(self._out_dir)
        self.lbl_dest.setText(self.lbl_dest.fontMetrics().elidedText(full, Qt.ElideMiddle, 320))
        self.lbl_dest.setToolTip(full)

    def _import_batch_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Batch Script",
            "",
            "Batch Files (*.txt *.csv *.srt);;Text Files (*.txt);;CSV Files (*.csv);;Subtitles (*.srt)",
        )
        if not file_path:
            return

        path_obj = Path(file_path)
        self.jobs = BatchWorker.parse_file(path_obj)
        self._populate_table()
        self.btn_start.setEnabled(len(self.jobs) > 0)
        self.lbl_status.setText(f"Loaded {len(self.jobs)} items from {path_obj.name}")

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self.jobs))
        self.lbl_empty.setVisible(not self.jobs)
        for row, job in enumerate(self.jobs):
            self.table.setItem(row, 0, QTableWidgetItem(str(job.item_index)))
            self.table.setItem(row, 1, QTableWidgetItem(job.output_filename))
            self.table.setItem(row, 2, QTableWidgetItem(job.text))
            self.table.setItem(row, 3, QTableWidgetItem(job.status.capitalize()))
            self.table.setItem(row, 4, QTableWidgetItem(f"{job.duration_seconds:.2f}s" if job.duration_seconds > 0 else "--"))

    def _start_batch(self) -> None:
        if self.is_busy():
            return
        profile_id = self.combo_voices.currentData()
        if not profile_id:
            QMessageBox.warning(self, "No Voice", "Please select a voice profile.")
            return

        profile = voice_repo.get_profile_by_id(profile_id)
        if not profile or not profile.primary_audio_path:
            QMessageBox.warning(self, "Missing Audio", "Voice profile has no reference clip.")
            return

        engine_name = self.combo_engine.currentText()
        engine = engine_registry.get_engine(engine_name)
        if not engine:
            return

        out_dir = self._out_dir
        params = engine.get_default_params()
        params.language = profile.language or params.language
        params.enable_watermark = config_manager.config.enable_audio_watermark

        for job in self.jobs:
            job.status = "pending"
        self._populate_table()
        self.progress_bar.setValue(0)

        self.worker = BatchWorker(
            engine=engine,
            jobs=self.jobs,
            reference_audio_path=profile.primary_audio_path,
            params=params,
            output_directory=out_dir,
            export_format=config_manager.config.default_export_format,
        )

        self.worker.item_started.connect(self._on_item_started)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.item_failed.connect(self._on_item_failed)
        self.worker.batch_progress.connect(self._on_batch_progress)
        self.worker.batch_finished.connect(self._on_batch_finished)
        self.worker.batch_error.connect(lambda msg: QMessageBox.critical(self, "Batch Failed", msg))

        self._set_running(True)
        self.activity.emit()
        self.worker.start()

    def _stop_batch(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.lbl_status.setText("Stopping queue")

    def _on_item_started(self, idx: int, filename: str) -> None:
        item = self.table.item(idx, 3)
        if item:
            item.setText("Running")
            item.setForeground(status_brush("warn"))

    def _on_item_finished(self, idx: int, out_path: str, duration: float) -> None:
        st_item = self.table.item(idx, 3)
        if st_item:
            st_item.setText("Done")
            st_item.setForeground(status_brush("ok"))

        dur_item = self.table.item(idx, 4)
        if dur_item:
            dur_item.setText(f"{duration:.2f}s")

    def _on_item_failed(self, idx: int, error_msg: str) -> None:
        item = self.table.item(idx, 3)
        if item:
            item.setText(f"Failed: {error_msg}")
            item.setForeground(status_brush("err"))

    def _on_batch_progress(self, completed: int, total: int, percent: float) -> None:
        self.progress_bar.setValue(int(percent))
        self.lbl_status.setText(f"Processing item {completed} of {total} ({percent:.1f}%)")

    def _on_batch_finished(self, success_count: int, fail_count: int) -> None:
        self._set_running(False)
        self.activity.emit()
        self.lbl_status.setText(f"Batch completed: {success_count} succeeded, {fail_count} failed.")
        QMessageBox.information(
            self,
            "Batch Complete",
            f"Finished batch synthesis.\nSuccess: {success_count}\nFailures: {fail_count}",
        )

