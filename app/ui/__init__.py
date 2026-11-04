"""
User interface components: main window, views, custom widgets, and dialogs.
"""

from app.ui.batch_view import BatchView
from app.ui.history_view import HistoryView
from app.ui.main_window import MainWindow
from app.ui.models_view import ModelsView
from app.ui.settings_view import SettingsView
from app.ui.studio_view import StudioView
from app.ui.voices_view import VoicesView

__all__ = [
    "MainWindow",
    "StudioView",
    "VoicesView",
    "BatchView",
    "HistoryView",
    "ModelsView",
    "SettingsView",
]

