"""
Mandatory Ethics, Consent & Acceptable Use Policy dialog.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

try:
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import (  # type: ignore
        QCheckBox,
        QDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QTextBrowser,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QDialog: pass
    class QWidget: pass

from app.core.config import config_manager
from app.core.logging_setup import get_logger

logger = get_logger("consent_dialog")

ACCEPTABLE_USE_TEXT = """
<h2>Voice Cloning Ethical Guidelines & Acceptable Use Policy</h2>
<p>Voice cloning technology synthesizes speech in realistic human voices. To prevent misuse, all users of VoiceClone Studio must abide by the following mandatory conditions:</p>

<ol>
  <li><b>Explicit Permission & Ownership:</b> You must possess explicit, verifiable permission from the individual whose voice you are cloning, or you must be the legal owner of the voice.</li>
  <li><b>Strict Prohibition Against Impersonation & Fraud:</b> You shall NOT synthesize voices for any of the following deceptive purposes:
    <ul>
      <li>Social engineering, fraud, phishing, or financial extortion;</li>
      <li>Impersonating public officials, politicians, law enforcement, or private citizens;</li>
      <li>Distributing deceptive political propaganda, election interference, or synthetic media intended to deceive;</li>
      <li>Harassment, defamation, abuse, or unauthorized non-consensual voice generation.</li>
    </ul>
  </li>
  <li><b>Watermarking & Provenance:</b> Speech synthesized using VoiceClone Studio embeds cryptographic audio watermarks (Perth) and metadata tags certifying AI generation. Any attempt to alter, strip, or defeat safety watermarks is strictly prohibited.</li>
  <li><b>Local Audit Logging:</b> Voice profiles record a verifiable consent timestamp stored in your local application database.</li>
</ol>
"""


class ConsentDialog(QDialog):
    """Modal dialog displaying ethics terms and requiring explicit agreement."""

    def __init__(self, parent: Optional[QWidget] = None, is_first_run: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("VoiceClone Studio — Ethics & Acceptable Use")
        self.setMinimumSize(720, 500)
        self.setModal(True)
        self.is_first_run = is_first_run

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Policy Text Browser
        self.text_browser = QTextBrowser(self)
        self.text_browser.setHtml(ACCEPTABLE_USE_TEXT)
        layout.addWidget(self.text_browser)

        # Consent Checkbox
        self.consent_checkbox = QCheckBox(
            "I own this voice or have the speaker's explicit permission, and I agree to the Acceptable Use terms.",
            self,
        )
        self.consent_checkbox.setStyleSheet("font-weight: 600;")
        self.consent_checkbox.toggled.connect(self._on_consent_toggled)
        layout.addWidget(self.consent_checkbox)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Decline && Exit" if is_first_run else "Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_accept = QPushButton("Accept && Proceed", self)
        self.btn_accept.setObjectName("primaryButton")
        self.btn_accept.setEnabled(False)
        self.btn_accept.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.btn_accept)

        layout.addLayout(btn_layout)

    def _on_consent_toggled(self, checked: bool) -> None:
        self.btn_accept.setEnabled(checked)

    def _on_accept(self) -> None:
        if self.is_first_run:
            config_manager.config.global_ethics_consent = True
            config_manager.config.consent_timestamp = datetime.utcnow().isoformat()
            config_manager.save()
            logger.info("User accepted global ethics consent on first run.")
        self.accept()

