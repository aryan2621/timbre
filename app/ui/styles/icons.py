"""
Drawn icon set (24px grid, 1.75 stroke, round caps) rendered from inline SVG.

Icons are re-tinted from the active theme tokens, so a theme switch only needs `refresh_icons()`.
Use `bind_icon(widget, "play")` instead of emoji or unicode glyphs in labels.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple
import weakref

from PySide6.QtCore import QByteArray, QSize, Qt  # type: ignore
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap  # type: ignore
from PySide6.QtSvg import QSvgRenderer  # type: ignore
from PySide6.QtWidgets import QAbstractButton, QLabel  # type: ignore

from app.core.paths import paths

_PATHS: Dict[str, str] = {
    "mic": '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><path d="M12 19v3"/>',
    "waveform": '<path d="M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3"/>',
    "voices": '<circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 0 0-16 0"/>',
    "batch": '<path d="m12 2 10 5-10 5L2 7l10-5Z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "history": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "models": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5M12 22V12"/>',
    "settings": '<path d="M21 4h-7M10 4H3M21 12h-9M8 12H3M21 20h-5M12 20H3M14 2v4M8 10v4M16 18v4"/>',
    "play": '<path d="M6 3 20 12 6 21Z"/>',
    "pause": '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "export": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1Z"/><path d="m9 12 2 2 4-4"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "plus": '<path d="M5 12h14M12 5v14"/>',
    "trash": '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "chevron-up": '<path d="m18 15-6-6-6 6"/>',
    "volume": '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
}

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
    'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)
_SCALE = 2  # render at 2x and tag the pixmap so icons stay sharp on HiDPI

_pixmap_cache: Dict[Tuple[str, str, int], QPixmap] = {}


def pixmap(name: str, color: str, size: int = 18, stroke: float = 1.75) -> QPixmap:
    key = (name, color, size)
    if key not in _pixmap_cache:
        svg = _SVG.format(c=color, w=stroke, body=_PATHS[name]).encode()
        renderer = QSvgRenderer(QByteArray(svg))
        image = QImage(size * _SCALE, size * _SCALE, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        pm = QPixmap.fromImage(image)
        pm.setDevicePixelRatio(_SCALE)
        _pixmap_cache[key] = pm
    return _pixmap_cache[key]


def asset_path(name: str, color: str, size: int = 12) -> str:
    """PNG on disk for QSS `image: url(...)` (QSS can't take in-memory pixmaps)."""
    out_dir = paths.temp_dir / "theme-assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{name}-{color.lstrip('#')}-{size}.png"
    if not target.exists():
        pixmap(name, color, size, stroke=2.25).save(str(target), "PNG")
    return target.as_posix()


# widget -> (icon name, off-colour token, on-colour token or None, size)
_bound: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def bind_icon(widget, name: str, off: str = "text_muted", on: Optional[str] = None, size: int = 18) -> None:
    """Gives a button or label a themed icon, and re-tints it whenever the theme changes."""
    _bound[widget] = (name, off, on, size)
    _apply(widget)


def refresh_icons() -> None:
    for widget in list(_bound.keys()):
        _apply(widget)


def _apply(widget) -> None:
    from app.ui.styles.theme import current_tokens  # late import: theme imports this module

    name, off, on, size = _bound[widget]
    t = current_tokens()
    if isinstance(widget, QLabel):
        widget.setPixmap(pixmap(name, getattr(t, off), size))
        return
    if isinstance(widget, QAbstractButton):
        icon = QIcon()
        icon.addPixmap(pixmap(name, getattr(t, off), size), QIcon.Normal, QIcon.Off)
        icon.addPixmap(pixmap(name, getattr(t, on or off), size), QIcon.Normal, QIcon.On)
        icon.addPixmap(pixmap(name, t.text_faint, size), QIcon.Disabled, QIcon.Off)
        widget.setIcon(icon)
        widget.setIconSize(QSize(size, size))
