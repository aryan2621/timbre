"""
Voice Library View: Speaker profile inventory, audio previews, clip management,
and 'New Voice' wizard trigger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QHBoxLayout,
        QHeaderView,
        QLabel,
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
from app.ui.styles.theme import configure_table, status_brush
from app.core.logging_setup import get_logger
from app.data.models import VoiceProfile
from app.data.voice_repo import voice_repo
from app.ui.dialogs.voice_wizard import VoiceWizardDialog

logger = get_logger("voices_view")


class VoicesView(QWidget):
    """Manages speaker voice profiles, reference audio clips, and creation wizard."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.player = AudioPlayer()
        self._build_ui()
        self.refresh_profiles()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Top Header Bar
        top_layout = QHBoxLayout()
        header_lbl = QLabel("Voice Library")
        header_lbl.setObjectName("pageHeader")
        top_layout.addWidget(header_lbl)

        top_layout.addStretch()

        self.btn_new_voice = QPushButton("New voice profile")
        self.btn_new_voice.setObjectName("primaryButton")
        bind_icon(self.btn_new_voice, "plus", off="on_accent", size=16)
        self.btn_new_voice.setToolTip("Launch the step-by-step voice calibration wizard.")
        self.btn_new_voice.clicked.connect(self._open_new_voice_wizard)
        top_layout.addWidget(self.btn_new_voice)

        layout.addLayout(top_layout)

        # Profiles Table
        self.table = QTableWidget(self)
        configure_table(self.table)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Voice", "Language", "Clips", "Quality", "Consent", ""
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 220)  # fits Preview + Delete (cell widgets don't drive auto-sizing)
        layout.addWidget(self.table)
        self.lbl_empty = QLabel("No voices yet. Create a voice profile to start cloning.")
        self.lbl_empty.setObjectName("mutedText")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_empty)

    def refresh_profiles(self) -> None:
        """Fetches all profiles from SQLite repository and populates the table."""
        profiles = voice_repo.list_all_profiles()
        self.table.setRowCount(len(profiles))
        self.lbl_empty.setVisible(not profiles)

        for row, p in enumerate(profiles):
            self.table.setItem(row, 0, QTableWidgetItem(str(p.id)))
            self.table.setItem(row, 1, QTableWidgetItem(p.name))
            self.table.setItem(row, 2, QTableWidgetItem(p.language.upper()))
            self.table.setItem(row, 3, QTableWidgetItem(f"{len(p.clips)} clips"))

            # Quality Score from primary clip
            quality = p.clips[0].quality_score if p.clips else 0
            self.table.setItem(row, 4, QTableWidgetItem(f"{quality}/100"))

            # Consent status
            consent_str = "Confirmed" if p.consent_confirmed else "Unconfirmed"
            item_consent = QTableWidgetItem(consent_str)
            item_consent.setForeground(status_brush("ok") if p.consent_confirmed else status_brush("err"))
            self.table.setItem(row, 5, item_consent)

            # Action Buttons widget
            actions_widget = QWidget()
            actions_widget.setObjectName("cell")
            act_layout = QHBoxLayout(actions_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_play = QPushButton("Preview")
            btn_play.setObjectName("rowButton")
            bind_icon(btn_play, "play", off="text", size=14)
            btn_play.clicked.connect(lambda _, prof=p: self._play_profile(prof))
            act_layout.addWidget(btn_play)

            btn_del = QPushButton("Delete")
            btn_del.setObjectName("rowButton")
            btn_del.setProperty("danger", True)
            bind_icon(btn_del, "trash", off="err", size=14)
            btn_del.clicked.connect(lambda _, pid=p.id, name=p.name: self._delete_profile(pid, name))
            act_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 6, actions_widget)

    def _play_profile(self, profile: VoiceProfile) -> None:
        clip_path = profile.primary_audio_path
        if not clip_path or not Path(clip_path).exists():
            QMessageBox.warning(self, "Clip Missing", f"Reference clip for '{profile.name}' not found on disk.")
            return

        self.player.load_file(clip_path)
        self.player.play()

    def _delete_profile(self, profile_id: Optional[int], name: str) -> None:
        if not profile_id:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Voice Profile Deletion",
            f"Are you sure you want to delete profile '{name}' and its stored audio clips?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            voice_repo.delete_profile(profile_id)
            self.refresh_profiles()

    def _open_new_voice_wizard(self) -> None:
        wizard = VoiceWizardDialog(self)
        wizard.voice_created.connect(lambda _: self.refresh_profiles())
        wizard.exec()
        wizard.deleteLater()

