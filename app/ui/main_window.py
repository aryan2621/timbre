"""
Main Application Window: Sidebar navigation, status bar monitoring,
keyboard shortcut orchestration, and global exception handling.
"""

from __future__ import annotations

import sys
import time
from typing import Optional

try:
    from PySide6.QtCore import QTimer, Qt  # type: ignore
    from PySide6.QtGui import QAction, QIcon, QKeySequence  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QApplication,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QStackedWidget,
        QStatusBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QMainWindow: pass
    class QWidget: pass

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.engines.registry import engine_registry
from app.ui.batch_view import BatchView
from app.ui.dialogs.consent import ConsentDialog
from app.ui.dialogs.onboarding import OnboardingDialog
from app.ui.history_view import HistoryView
from app.ui.models_view import ModelsView
from app.ui.settings_view import SettingsView
from app.ui.styles.icons import bind_icon, refresh_icons
from app.ui.styles.theme import get_theme_stylesheet
from app.ui.studio_view import StudioView
from app.ui.voices_view import VoicesView

logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """VoiceClone Studio top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VoiceClone Studio — Zero-Shot Local Speech Synthesis")
        self.setMinimumSize(1024, 720)
        self.resize(1200, 800)

        self._last_activity_time = time.time()
        self._apply_theme(config_manager.config.theme)  # first, so widgets build with the right tokens
        self._build_ui()
        self._setup_shortcuts()
        self._setup_status_bar()
        self._setup_idle_timer()
        self.studio_view.txt_input.setFocus()  # otherwise the first sidebar button grabs focus and shows a ring

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        sidebar = QWidget(self)
        sidebar.setObjectName("sidebar")
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(8, 16, 8, 16)
        s_layout.setSpacing(6)

        # App Brand Title
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(16, 4, 8, 14)
        brand_row.setSpacing(8)
        brand_icon = QLabel()
        bind_icon(brand_icon, "mic", off="accent", size=20)
        brand_lbl = QLabel("VoiceClone")
        brand_lbl.setObjectName("brandLabel")
        brand_row.addWidget(brand_icon)
        brand_row.addWidget(brand_lbl)
        brand_row.addStretch()
        s_layout.addLayout(brand_row)

        # Nav Buttons
        self.nav_buttons = []
        self.btn_nav_studio = self._create_nav_btn("Studio", 0, "waveform")
        self.btn_nav_voices = self._create_nav_btn("Voices", 1, "voices")
        self.btn_nav_batch = self._create_nav_btn("Batch", 2, "batch")
        self.btn_nav_history = self._create_nav_btn("History", 3, "history")
        self.btn_nav_models = self._create_nav_btn("Models", 4, "models")
        self.btn_nav_settings = self._create_nav_btn("Settings", 5, "settings")

        for btn in [
            self.btn_nav_studio,
            self.btn_nav_voices,
            self.btn_nav_batch,
            self.btn_nav_history,
            self.btn_nav_models,
            self.btn_nav_settings,
        ]:
            s_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        s_layout.addStretch()

        # Offline Status Badge
        offline_row = QHBoxLayout()
        offline_row.setContentsMargins(16, 8, 8, 4)
        offline_row.setSpacing(8)
        offline_icon = QLabel()
        bind_icon(offline_icon, "shield", off="ok", size=16)
        lbl_offline = QLabel("Runs 100% offline")
        lbl_offline.setObjectName("okText")
        lbl_offline.setStyleSheet("font-size: 12px;")
        offline_row.addWidget(offline_icon)
        offline_row.addWidget(lbl_offline)
        offline_row.addStretch()
        s_layout.addLayout(offline_row)

        root_layout.addWidget(sidebar)

        # 2. Main Stacked Views
        self.stack = QStackedWidget(self)
        self.studio_view = StudioView(self)
        self.voices_view = VoicesView(self)
        self.batch_view = BatchView(self)
        self.history_view = HistoryView(self)
        self.models_view = ModelsView(self)
        self.settings_view = SettingsView(self)
        self.settings_view.theme_changed.connect(self._apply_theme)
        self.settings_view.is_busy = self._jobs_running
        self.studio_view.activity.connect(self._touch_activity)
        self.batch_view.activity.connect(self._touch_activity)

        self.stack.addWidget(self.studio_view)    # Index 0
        self.stack.addWidget(self.voices_view)    # Index 1
        self.stack.addWidget(self.batch_view)     # Index 2
        self.stack.addWidget(self.history_view)   # Index 3
        self.stack.addWidget(self.models_view)    # Index 4
        self.stack.addWidget(self.settings_view)  # Index 5

        root_layout.addWidget(self.stack, 1)

        # Select Studio View by default
        self._switch_view(0)

    def _create_nav_btn(self, title: str, index: int, icon_name: str) -> QPushButton:
        btn = QPushButton(title)
        bind_icon(btn, icon_name, off="text_muted", on="accent", size=18)
        btn.setCheckable(True)
        btn.setFocusPolicy(Qt.TabFocus)  # keyboard users still get the ring; mouse clicks don't
        btn.clicked.connect(lambda: self._switch_view(index))
        return btn

    def _switch_view(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

        # Auto-refresh on view change
        if index == 0:
            self.studio_view._refresh_voices()
        elif index == 1:
            self.voices_view.refresh_profiles()
        elif index == 2:
            self.batch_view._refresh_voices()
        elif index == 3:
            self.history_view.refresh_history()
        elif index == 4:
            self.models_view.refresh_table()

    def _setup_shortcuts(self) -> None:
        """Global keyboard shortcuts."""
        # Generate: Ctrl+Return / Cmd+Return
        # Scoped to the Studio page so Space/Ctrl+S don't fire from other tabs.
        for keys, slot in (
            ("Ctrl+Return", self.studio_view.start_generation),
            ("Space", self.studio_view.toggle_playback),
            ("Ctrl+S", self.studio_view.export_audio),
        ):
            act = QAction(self.studio_view)
            act.setShortcut(QKeySequence(keys))
            act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            act.triggered.connect(slot)
            self.studio_view.addAction(act)

    def _setup_status_bar(self) -> None:
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)

        self.lbl_sb_device = QLabel("Device: Initializing")
        self.lbl_sb_vram = QLabel("VRAM: --")
        self.lbl_sb_model = QLabel("Loaded: None")

        status_bar.addWidget(self.lbl_sb_device)
        status_bar.addWidget(self.lbl_sb_vram)
        status_bar.addPermanentWidget(self.lbl_sb_model)

        self._update_hardware_status()

    def _update_hardware_status(self) -> None:
        info = device_manager.get_device_info()
        self.lbl_sb_device.setText(f"Device: {info.device_type.upper()}")
        if info.total_memory_mb > 0:
            self.lbl_sb_vram.setText(f"VRAM: {info.allocated_memory_mb:.0f}/{info.total_memory_mb:.0f} MB")
        else:
            self.lbl_sb_vram.setText(f"VRAM: N/A ({info.device_type.upper()})")

        loaded = [e.name for e in engine_registry.get_all_engines() if e.is_loaded()]
        self.lbl_sb_model.setText(f"Loaded: {', '.join(loaded) if loaded else 'None'}")

    def _setup_idle_timer(self) -> None:
        """Monitors idle time to unload models and free GPU memory."""
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(30000)  # Check every 30 seconds
        self.idle_timer.timeout.connect(self._check_idle_unload)
        self.idle_timer.start()

    def _touch_activity(self) -> None:
        self._last_activity_time = time.time()

    def _jobs_running(self) -> bool:
        return self.studio_view.is_busy() or self.batch_view.is_busy()

    def closeEvent(self, event) -> None:
        """Stop playback and join worker threads so no QThread is destroyed while running."""
        self.idle_timer.stop()
        for view in (self.studio_view, self.batch_view, self.models_view):
            view.shutdown()
        for view in (self.voices_view, self.history_view):
            if hasattr(view, "player"):
                view.player.stop()
        super().closeEvent(event)

    def _check_idle_unload(self) -> None:
        self._update_hardware_status()
        if self._jobs_running():
            self._touch_activity()
            return
        unload_mins = config_manager.config.idle_unload_minutes
        if unload_mins <= 0:
            return

        elapsed_mins = (time.time() - self._last_activity_time) / 60.0
        if elapsed_mins >= unload_mins:
            loaded_any = any(e.is_loaded() for e in engine_registry.get_all_engines())
            if loaded_any:
                logger.info("Unloading models due to %d minutes of inactivity.", unload_mins)
                engine_registry.unload_all()
                self._update_hardware_status()

    def _apply_theme(self, theme_name: str) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_theme_stylesheet(theme_name))
            refresh_icons()  # tokens changed: re-tint every drawn icon

    def check_first_run_dialogs(self) -> None:
        """Prompts for mandatory ethics consent and onboarding tour if first run."""
        cfg = config_manager.config
        if not cfg.global_ethics_consent:
            consent_dlg = ConsentDialog(self, is_first_run=True)
            res = consent_dlg.exec()
            if res != ConsentDialog.Accepted:
                logger.info("User declined first-run consent. Exiting.")
                sys.exit(0)

        if not cfg.first_run_completed:
            tour_dlg = OnboardingDialog(self)
            tour_dlg.exec()

