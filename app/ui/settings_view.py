"""
Settings View: Application preferences, compute hardware, audio I/O devices,
safety watermarking, and logging configuration.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Optional

try:
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QCheckBox,
        QComboBox,
        QFileDialog,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSlider,
        QSpinBox,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QWidget: pass

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.engines.registry import engine_registry
from app.ui.styles.theme import status_color

logger = get_logger("settings_view")


class SettingsView(QWidget):
    """Configuration panel for hardware, theme, audio devices, and safety."""

    theme_changed = Signal(str)  # Emits new theme name

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.is_busy = lambda: False  # replaced by MainWindow with a "jobs running" check
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 16, 16, 16)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        container.setMaximumWidth(760)  # keep form controls a readable width on wide windows
        layout = QVBoxLayout(container)
        header_lbl = QLabel("Settings")
        header_lbl.setObjectName("pageHeader")
        layout.addWidget(header_lbl)
        layout.setSpacing(16)

        # 1. Appearance & Theme
        grp_theme = QGroupBox("Appearance && Accessibility")
        t_form = QFormLayout(grp_theme)
        self.combo_theme = QComboBox()
        for label, key in (("Dark", "dark"), ("Light", "light"), ("High Contrast", "high_contrast")):
            self.combo_theme.addItem(label, userData=key)
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        t_form.addRow("Color Theme:", self.combo_theme)
        layout.addWidget(grp_theme)

        # 2. Hardware & Device Performance
        grp_hw = QGroupBox("Hardware && Acceleration")
        hw_layout = QVBoxLayout(grp_hw)

        info = device_manager.get_device_info()
        hw_info_str = f"<b>Detected Device:</b> {info.device_name} ({info.device_type.upper()})<br>"
        if info.total_memory_mb > 0:
            hw_info_str += f"<b>Total VRAM:</b> {info.total_memory_mb:.0f} MB | <b>Free:</b> {info.free_memory_mb:.0f} MB<br>"
        if info.warning_message:
            hw_info_str += f"<span style='color:{status_color('warn')};'><b>Note:</b> {info.warning_message}</span>"

        lbl_hw = QLabel(hw_info_str)
        lbl_hw.setStyleSheet("line-height: 1.4; padding: 4px;")
        hw_layout.addWidget(lbl_hw)

        hw_form = QFormLayout()
        self.combo_device = QComboBox()
        self.combo_device.addItems(["auto", "cuda", "mps", "cpu"])
        hw_form.addRow("Device Preference:", self.combo_device)

        self.chk_fp16 = QCheckBox("Enable Half-Precision (fp16 / bf16) to conserve VRAM")
        hw_form.addRow("Precision:", self.chk_fp16)

        self.spin_idle = QSpinBox()
        self.spin_idle.setRange(0, 60)
        self.spin_idle.setSuffix(" minutes (0 to disable)")
        hw_form.addRow("Unload model when idle:", self.spin_idle)

        self.chk_clear_cache = QCheckBox(
            "Free GPU memory cache after every render (slower, frees VRAM)"
        )
        self.chk_clear_cache.setToolTip(
            "Purging the CUDA/MPS allocator cache after each job makes the next "
            "render re-allocate its blocks. Leave this off for repeated renders."
        )
        hw_form.addRow("Memory:", self.chk_clear_cache)

        hw_layout.addLayout(hw_form)

        btn_purge_cache = QPushButton("Purge GPU Memory Cache")
        btn_purge_cache.clicked.connect(self._purge_gpu_cache)
        hw_layout.addWidget(btn_purge_cache)

        layout.addWidget(grp_hw)

        # 3. Audio Devices & Export Defaults
        grp_audio = QGroupBox("Audio I/O && Export Settings")
        a_form = QFormLayout(grp_audio)

        self.combo_export_fmt = QComboBox()
        self.combo_export_fmt.addItems(["wav", "mp3", "flac", "ogg"])
        a_form.addRow("Default Export Format:", self.combo_export_fmt)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(40, 400)
        self.spin_chunk.setSingleStep(10)
        self.spin_chunk.setSuffix(" characters")
        self.spin_chunk.setToolTip(
            "How much text is rendered in one pass. Smaller chunks render faster "
            "and start playing sooner; larger chunks sound more continuous."
        )
        a_form.addRow("Chunk size:", self.spin_chunk)

        layout.addWidget(grp_audio)

        # 4. Ethics, Provenance & Watermarking
        grp_safety = QGroupBox("Safety, Provenance && Watermarking")
        s_layout = QVBoxLayout(grp_safety)

        self.chk_watermark = QCheckBox("Enable Perth Audio Watermark (Imperceptible acoustic signature)")
        self.chk_watermark.setChecked(True)
        s_layout.addWidget(self.chk_watermark)

        lbl_safety_notice = QLabel(
            "Note: Ethical watermarking is enabled by default to prevent voice misuse and "
            "comply with safety and provenance standards."
        )
        lbl_safety_notice.setObjectName("mutedText")
        lbl_safety_notice.setStyleSheet("font-size: 11px;")
        lbl_safety_notice.setWordWrap(True)
        s_layout.addWidget(lbl_safety_notice)

        layout.addWidget(grp_safety)

        # 5. File System Paths & Logs
        grp_paths = QGroupBox("Storage Directories && Logs")
        p_form = QFormLayout(grp_paths)

        self.lbl_log_path = QLabel(str(paths.log_file_path))
        self.lbl_log_path.setObjectName("mutedText")
        self.lbl_log_path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # long paths must not widen the page
        self.lbl_log_path.setToolTip(str(paths.log_file_path))
        self.lbl_log_path.setStyleSheet("font-size: 11px;")
        p_form.addRow("Log File:", self.lbl_log_path)

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        p_form.addRow("Log Level:", self.combo_log_level)

        btn_open_logs = QPushButton("Open Logs Folder")
        btn_open_logs.clicked.connect(self._open_log_folder)
        p_form.addRow("", btn_open_logs)

        layout.addWidget(grp_paths)

        # Save Button
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._save_settings)
        layout.addWidget(self.btn_save)

        layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _load_values(self) -> None:
        cfg = config_manager.config
        idx_t = self.combo_theme.findData(cfg.theme.lower())
        if idx_t >= 0:
            self.combo_theme.setCurrentIndex(idx_t)

        idx_d = self.combo_device.findText(cfg.device_preference)
        if idx_d >= 0:
            self.combo_device.setCurrentIndex(idx_d)

        self.chk_fp16.setChecked(cfg.use_half_precision)
        self.spin_idle.setValue(cfg.idle_unload_minutes)
        self.chk_clear_cache.setChecked(cfg.clear_device_cache_after_job)

        idx_f = self.combo_export_fmt.findText(cfg.default_export_format)
        if idx_f >= 0:
            self.combo_export_fmt.setCurrentIndex(idx_f)
        self.spin_chunk.setValue(cfg.max_chars_per_chunk)

        self.chk_watermark.setChecked(cfg.enable_audio_watermark)

        idx_l = self.combo_log_level.findText(cfg.log_level)
        if idx_l >= 0:
            self.combo_log_level.setCurrentIndex(idx_l)

    def _save_settings(self) -> None:
        cfg = config_manager.config
        cfg.theme = self.combo_theme.currentData()
        cfg.device_preference = self.combo_device.currentText()
        cfg.use_half_precision = self.chk_fp16.isChecked()
        cfg.idle_unload_minutes = self.spin_idle.value()
        cfg.clear_device_cache_after_job = self.chk_clear_cache.isChecked()
        cfg.default_export_format = self.combo_export_fmt.currentText()
        cfg.max_chars_per_chunk = self.spin_chunk.value()
        cfg.enable_audio_watermark = self.chk_watermark.isChecked()
        cfg.log_level = self.combo_log_level.currentText()

        config_manager.save()
        QMessageBox.information(self, "Settings Saved", "Preferences updated successfully.")

    def _on_theme_changed(self, _index: int) -> None:
        self.theme_changed.emit(self.combo_theme.currentData())

    def _purge_gpu_cache(self) -> None:
        if self.is_busy():
            QMessageBox.information(self, "Busy", "A synthesis or batch job is running. Try again when it finishes.")
            return
        device_manager.clear_cache()
        engine_registry.unload_all()
        QMessageBox.information(self, "Cache Cleared", "VRAM and device memory allocations have been freed.")

    def _open_log_folder(self) -> None:
        log_dir = paths.log_dir
        if sys.platform == "darwin":
            os.system(f'open "{log_dir}"')
        elif sys.platform == "win32":
            os.system(f'explorer "{log_dir}"')
        else:
            os.system(f'xdg-open "{log_dir}"')

