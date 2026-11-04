"""
First-run interactive onboarding walkthrough dialog.
"""

from __future__ import annotations

from typing import Optional

try:
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QDialog: pass
    class QWidget: pass

from app.core.config import config_manager


class OnboardingDialog(QDialog):
    """Multi-page introductory tour explaining key features on first startup."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to VoiceClone Studio")
        self.setFixedSize(540, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.stack = QStackedWidget(self)

        # Page 1: Welcome & Offline Guarantee
        self.stack.addWidget(self._create_page(
            title="Welcome to VoiceClone Studio",
            subtitle="100% Local, Private, Offline Speech Synthesis",
            body=(
                "VoiceClone Studio enables zero-shot voice cloning directly on your personal computer.\n\n"
                "• No Cloud APIs: Everything runs locally on your CPU or GPU.\n"
                "• Zero Telemetry: Your voice recordings and synthesized audio never leave your device.\n"
                "• Pluggable Engines: Choose between Chatterbox TTS (MIT), XTTS v2, and F5-TTS."
            ),
        ))

        # Page 2: Creating Voices
        self.stack.addWidget(self._create_page(
            title="Voice Calibration & Best Practices",
            subtitle="Capturing Clean Reference Audio",
            body=(
                "To get the highest quality clone:\n\n"
                "1. Provide 5 to 30 seconds of clean, continuous speech.\n"
                "2. Minimize background hiss, fan noise, and room reverb.\n"
                "3. Use the built-in microphone recorder with phonetically balanced sentences.\n"
                "4. Enable automated silence trimming (VAD) and loudness normalization (-23 LUFS)."
            ),
        ))

        # Page 3: Studio & Controls
        self.stack.addWidget(self._create_page(
            title="Studio Controls & Workflow",
            subtitle="Sentence Chunking & Expressive Synthesis",
            body=(
                "• Long Text: Texts are automatically divided into natural sentence chunks with crossfades.\n"
                "• Parameters: Fine-tune exaggeration, emotion, CFG weight, and speed.\n"
                "• Waveform Scrubber: Review audio with instant seek and multi-format export (WAV, MP3, FLAC, OGG).\n"
                "• Batch Mode: Synthesize hundreds of lines from text, CSV, or SRT files."
            ),
        ))

        layout.addWidget(self.stack)

        # Bottom Navigation
        btn_layout = QHBoxLayout()
        self.step_label = QLabel("Step 1 of 3", self)
        self.step_label.setObjectName("mutedText")
        self.step_label.setStyleSheet("font-weight: 500;")
        btn_layout.addWidget(self.step_label)

        btn_layout.addStretch()

        self.btn_back = QPushButton("Back", self)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._prev_page)
        btn_layout.addWidget(self.btn_back)

        self.btn_next = QPushButton("Next", self)
        self.btn_next.setObjectName("primaryButton")
        self.btn_next.clicked.connect(self._next_page)
        btn_layout.addWidget(self.btn_next)

        layout.addLayout(btn_layout)

    def _create_page(self, title: str, subtitle: str, body: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(t_lbl)

        s_lbl = QLabel(subtitle)
        s_lbl.setObjectName("stepLabel")
        layout.addWidget(s_lbl)

        b_lbl = QLabel(body)
        b_lbl.setWordWrap(True)
        b_lbl.setStyleSheet("font-size: 13px; line-height: 1.5;")
        layout.addWidget(b_lbl)

        layout.addStretch()
        return page

    def _update_nav(self) -> None:
        idx = self.stack.currentIndex()
        tot = self.stack.count()
        self.step_label.setText(f"Step {idx + 1} of {tot}")
        self.btn_back.setEnabled(idx > 0)
        self.btn_next.setText("Finish" if idx == tot - 1 else "Next")

    def _next_page(self) -> None:
        if self.stack.currentIndex() < self.stack.count() - 1:
            self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
            self._update_nav()
        else:
            config_manager.config.first_run_completed = True
            config_manager.save()
            self.accept()

    def _prev_page(self) -> None:
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._update_nav()

