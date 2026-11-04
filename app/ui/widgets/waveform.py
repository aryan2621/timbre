"""
Interactive audio waveform visualizer widget with scrub head and seek-on-click.
"""

from __future__ import annotations

from typing import Optional

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PySide6.QtCore import QPoint, QRectF, Qt, Signal  # type: ignore
    from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPainterPath, QPen  # type: ignore
    from PySide6.QtWidgets import QSizePolicy, QWidget  # type: ignore
except ImportError:
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
    class QWidget: pass


class WaveformWidget(QWidget):
    """Draws an interactive waveform display with an active playback playhead."""

    seek_requested = Signal(float)  # Emits target position in seconds

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setCursor(Qt.PointingHandCursor)

        self._audio_data: Optional[np.ndarray] = None
        self._sample_rate: int = 24000
        self._current_time: float = 0.0
        self._total_time: float = 0.0
        self._is_dragging: bool = False
        self._peaks: Optional[np.ndarray] = None  # per-pixel-column peaks, cached per width

        self.setMinimumHeight(120)

    def set_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Sets the audio waveform to visualize."""
        if audio is None or len(audio) == 0:
            self._audio_data = None
            self._total_time = 0.0
        else:
            mono = audio if audio.ndim == 1 else np.mean(audio, axis=-1)
            self._audio_data = mono.astype(np.float32)
            self._sample_rate = sample_rate
            self._total_time = len(mono) / sample_rate

        self._current_time = 0.0
        self._peaks = None
        self.update()

    def _column_peaks(self, width: int) -> np.ndarray:
        """Max |sample| per pixel column; computed once per (audio, width), not on every repaint."""
        if self._peaks is None or len(self._peaks) != width:
            edges = np.linspace(0, len(self._audio_data), width + 1).astype(int)
            self._peaks = np.maximum.reduceat(np.abs(self._audio_data), edges[:-1])
        return self._peaks

    def update_position(self, current_seconds: float, total_seconds: float) -> None:
        """Updates the current playback position playhead."""
        if current_seconds == self._current_time and (total_seconds <= 0 or total_seconds == self._total_time):
            return  # called from a 40 ms poll timer: skip repaints while nothing moves
        self._current_time = current_seconds
        if total_seconds > 0:
            self._total_time = total_seconds
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        from app.ui.styles.theme import current_tokens  # colours follow the active theme

        t = current_tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Recessed rounded panel
        panel = QPainterPath()
        panel.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)
        painter.fillPath(panel, QColor(t.inset))
        painter.setPen(QPen(QColor(t.border), t.border_width))
        painter.drawPath(panel)
        painter.setClipPath(panel)

        if self._audio_data is None or len(self._audio_data) == 0:
            painter.setPen(QColor(t.text_faint))
            painter.drawText(self.rect(), Qt.AlignCenter, "Rendered audio appears here")
            return

        peaks = self._column_peaks(w)
        half_h = h / 2.0
        playhead_x = (self._current_time / max(0.001, self._total_time)) * w

        # Draw waveform bars
        for x, peak in enumerate(peaks):
            bar_h = max(2.0, peak * (h * 0.85))

            # Played part in the accent colour, remainder muted
            painter.setPen(QPen(QColor(t.accent if x <= playhead_x else t.text_faint), 1.5))

            painter.drawLine(x, int(half_h - bar_h / 2), x, int(half_h + bar_h / 2))

        # Draw Playhead line
        painter.setPen(QPen(QColor(t.signal), 2.0))
        painter.drawLine(int(playhead_x), 0, int(playhead_x), h)

        # Draw current timestamp overlay in bottom-right corner
        cur_min, cur_sec = divmod(int(self._current_time), 60)
        tot_min, tot_sec = divmod(int(self._total_time), 60)
        time_str = f"{cur_min:02d}:{cur_sec:02d} / {tot_min:02d}:{tot_sec:02d}"

        painter.setPen(QColor(t.text_muted))
        painter.drawText(w - 112, h - 10, time_str)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._emit_seek(event.pos().x())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging:
            self._emit_seek(event.pos().x())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._is_dragging = False

    def _emit_seek(self, x: int) -> None:
        if self._total_time <= 0:
            return
        ratio = max(0.0, min(1.0, x / max(1, self.width())))
        seek_sec = ratio * self._total_time
        self._current_time = seek_sec
        self.update()
        self.seek_requested.emit(seek_sec)
