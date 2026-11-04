"""
Model Manager View: Offline model status, checksum verification,
download progress with HTTP resumption, and license notices.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict, List, Optional

try:
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QFileDialog,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMessageBox,
        QProgressBar,
        QSizePolicy,
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
from app.data.model_catalog import CATALOG_MODELS, is_model_present, model_local_path
from app.data.models import ModelMetadata
from app.workers.download_worker import ModelDownloadWorker

logger = get_logger("models_view")

# Shared with the HTTP sidecar: one source of truth for model metadata.

class ModelsView(QWidget):
    """Inspects and manages offline TTS model weights."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.download_workers: Dict[str, ModelDownloadWorker] = {}
        self._build_ui()
        self.refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Header Bar
        top_bar = QHBoxLayout()
        header_lbl = QLabel("Model Weight Manager (100% Offline Capability)")
        header_lbl.setObjectName("pageHeader")
        top_bar.addWidget(header_lbl)

        top_bar.addStretch()

        self.btn_change_dir = QPushButton("Change Storage Directory")
        self.btn_change_dir.clicked.connect(self._change_model_dir)
        top_bar.addWidget(self.btn_change_dir)

        layout.addLayout(top_bar)

        # Storage directory banner
        self.lbl_storage_dir = QLabel(f"Active Weights Cache: {config_manager.get_models_directory()}")
        self.lbl_storage_dir.setObjectName("mutedText")
        self.lbl_storage_dir.setStyleSheet("font-size: 12px; padding: 4px;")
        self.lbl_storage_dir.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # long paths must not widen the page
        self.lbl_storage_dir.setToolTip(str(config_manager.get_models_directory()))
        layout.addWidget(self.lbl_storage_dir)

        # Models Table
        self.table = QTableWidget(self)
        configure_table(self.table)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Model", "Version", "License", "Size", "Status", ""
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (1, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 150)
        layout.addWidget(self.table)

    def refresh_table(self) -> None:
        base_dir = config_manager.get_models_directory()
        self.table.setRowCount(len(CATALOG_MODELS))

        for row, m in enumerate(CATALOG_MODELS):
            model_path = model_local_path(m, base_dir)
            # Partial downloads (*.part) don't count as an installed model.
            is_present = is_model_present(m, base_dir)
            worker = self.download_workers.get(m.id)
            is_downloading = worker is not None and worker.isRunning()

            self.table.setItem(row, 0, QTableWidgetItem(m.name))
            self.table.setItem(row, 1, QTableWidgetItem(m.version))

            lic_item = QTableWidgetItem(m.license_name)
            if not m.commercial_allowed:
                lic_item.setForeground(status_brush("warn"))
            self.table.setItem(row, 2, lic_item)

            size_mb = m.total_bytes / (1024 * 1024)
            self.table.setItem(row, 3, QTableWidgetItem(f"{size_mb:.0f} MB"))

            status_str = "Downloading" if is_downloading else (
                "Ready" if is_present else "Not downloaded"
            )
            st_item = QTableWidgetItem(status_str)
            st_item.setForeground(status_brush("ok") if is_present else status_brush("muted"))
            self.table.setItem(row, 4, st_item)

            # Actions Widget
            act_widget = QWidget()
            act_widget.setObjectName("cell")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            if is_downloading:
                btn_dl = QPushButton("Downloading")
                btn_dl.setEnabled(False)
                act_layout.addWidget(btn_dl)
            elif is_present:
                btn_del = QPushButton("Delete")
                btn_del.setProperty("danger", True)
                bind_icon(btn_del, "trash", off="err", size=14)
                btn_del.clicked.connect(lambda _, d=model_path, name=m.name: self._delete_model(d, name))
                act_layout.addWidget(btn_del)
            else:
                btn_dl = QPushButton("Download")
                btn_dl.setObjectName("rowButton")
                btn_dl.setProperty("accent", True)
                bind_icon(btn_dl, "export", off="on_accent", size=14)
                btn_dl.clicked.connect(lambda _, model=m: self._start_download(model))
                act_layout.addWidget(btn_dl)

            self.table.setCellWidget(row, 5, act_widget)

    def is_busy(self) -> bool:
        return any(w.isRunning() for w in self.download_workers.values())

    def shutdown(self) -> None:
        """Cancels running downloads and waits for their threads (called on window close)."""
        for w in self.download_workers.values():
            if w.isRunning():
                w.cancel()
                w.wait()

    def _start_download(self, model: ModelMetadata) -> None:
        existing = self.download_workers.get(model.id)
        if existing is not None and existing.isRunning():
            return
        if not model.commercial_allowed:
            warn = QMessageBox.warning(
                self,
                "Non-Commercial License Notice",
                f"{model.name} is licensed under {model.license_name}.\n\n"
                f"{model.license_notice}\n\nDo you accept these license restrictions?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if warn != QMessageBox.Yes:
                return

        dest_folder = config_manager.get_models_directory() / model.local_dir
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_file = dest_folder / Path(model.download_url).name

        worker = ModelDownloadWorker(
            model_id=model.id,
            download_url=model.download_url,
            destination_path=dest_file,
            expected_sha256=model.expected_sha256,
        )

        worker.progress_updated.connect(self._on_download_progress)
        worker.download_finished.connect(self._on_download_finished)
        worker.download_failed.connect(self._on_download_failed)
        worker.finished.connect(self.refresh_table)  # runs after the thread has really ended

        self.download_workers[model.id] = worker
        worker.start()
        QMessageBox.information(
            self,
            "Download Started",
            f"Downloading {model.name} in background. You will be notified when complete.",
        )

    def _on_download_progress(self, model_id: str, percent: float, speed_mb_s: float, status_str: str) -> None:
        for row, m in enumerate(CATALOG_MODELS):
            if m.id == model_id:
                item = self.table.item(row, 4)
                if item:
                    item.setText(f"{percent:.0f}% — {status_str}")

    def _on_download_finished(self, model_id: str, local_path: str) -> None:
        self.refresh_table()
        QMessageBox.information(
            self,
            "Download Complete",
            f"Model {model_id} downloaded and verified successfully!\nSaved to: {local_path}",
        )

    def _on_download_failed(self, model_id: str, error_msg: str) -> None:
        self.refresh_table()
        QMessageBox.critical(self, "Download Error", f"Failed downloading {model_id}:\n{error_msg}")

    def _delete_model(self, model_dir: Path, name: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the local weights for '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            shutil.rmtree(model_dir, ignore_errors=True)
            self.refresh_table()

    def _change_model_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Model Weights Cache Directory")
        if folder:
            config_manager.config.custom_models_dir = folder
            config_manager.save()
            self.lbl_storage_dir.setText(f"Active Weights Cache: {folder}")
            self.refresh_table()

