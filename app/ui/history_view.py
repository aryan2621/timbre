"""
History View: Log of past speech generations, audio replay, parameter inspection,
re-generation, and export.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

try:
    from PySide6.QtCore import Qt, Signal  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QFileDialog,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QWidget: pass

from app.audio.player import AudioPlayer
from app.ui.styles.icons import bind_icon
from app.ui.styles.theme import configure_table
from app.core.logging_setup import get_logger
from app.data.history_repo import history_repo
from app.data.models import HistoryEntry

logger = get_logger("history_view")


class HistoryView(QWidget):
    """Browses past speech generations with replay, search, and export."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.player = AudioPlayer()
        self.entries: List[HistoryEntry] = []
        self._build_ui()
        self.refresh_history()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header & Search Bar
        top_bar = QHBoxLayout()
        header_lbl = QLabel("Generation History")
        header_lbl.setObjectName("pageHeader")
        top_bar.addWidget(header_lbl)

        top_bar.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search text or voice name")
        self.txt_search.setFixedWidth(240)
        self.txt_search.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.txt_search)

        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.clicked.connect(self._clear_all_history)
        top_bar.addWidget(self.btn_clear)

        layout.addLayout(top_bar)

        # History Table
        self.table = QTableWidget(self)
        configure_table(self.table)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Voice", "Engine", "Prompt Text", "Duration", "Seed", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 200)  # fits Play + Delete
        layout.addWidget(self.table)
        self.lbl_empty = QLabel("No generations yet. Synthesize something in the Studio tab.")
        self.lbl_empty.setObjectName("mutedText")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_empty)

    def refresh_history(self) -> None:
        query = self.txt_search.text().strip()
        if query:
            self.entries = history_repo.search(query)
        else:
            self.entries = history_repo.list_recent(limit=150)

        self.table.setRowCount(len(self.entries))
        self.lbl_empty.setVisible(not self.entries)
        for row, item in enumerate(self.entries):
            # Format timestamp
            date_str = item.created_at[:19].replace("T", " ")
            self.table.setItem(row, 0, QTableWidgetItem(date_str))
            self.table.setItem(row, 1, QTableWidgetItem(item.voice_name))
            self.table.setItem(row, 2, QTableWidgetItem(item.engine_name))

            # Prompt preview
            preview_text = item.prompt_text.replace("\n", " ")
            if len(preview_text) > 80:
                preview_text = preview_text[:77] + "..."
            self.table.setItem(row, 3, QTableWidgetItem(preview_text))

            self.table.setItem(row, 4, QTableWidgetItem(f"{item.duration_seconds:.2f}s"))
            self.table.setItem(row, 5, QTableWidgetItem(str(item.seed)))

            # Actions Widget
            act_widget = QWidget()
            act_widget.setObjectName("cell")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_play = QPushButton("Play")
            btn_play.setObjectName("rowButton")
            bind_icon(btn_play, "play", off="text", size=14)
            btn_play.clicked.connect(lambda _, path=item.audio_path: self._play_audio(path))
            act_layout.addWidget(btn_play)

            btn_del = QPushButton("Delete")
            btn_del.setObjectName("rowButton")
            btn_del.setProperty("danger", True)
            bind_icon(btn_del, "trash", off="err", size=14)
            btn_del.clicked.connect(lambda _, eid=item.id: self._delete_entry(eid))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 6, act_widget)

    def _on_search_changed(self) -> None:
        self.refresh_history()

    def _play_audio(self, path_str: str) -> None:
        if not path_str or not Path(path_str).exists():
            QMessageBox.warning(self, "Audio Missing", "The rendered audio file was deleted or moved.")
            return
        self.player.load_file(path_str)
        self.player.play()

    def _delete_entry(self, entry_id: Optional[int]) -> None:
        if not entry_id:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Entry",
            "Delete this history entry and its audio file?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            history_repo.delete_entry(entry_id)
            self.refresh_history()

    def _clear_all_history(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all generation logs and cached audio files?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            history_repo.clear_all()
            self.refresh_history()

