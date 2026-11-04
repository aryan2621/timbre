"""
Design system for VoiceClone Studio: a pro-audio graphite palette with one signal accent.

Three themes (dark, light, high-contrast) share a single QSS template; only the colour tokens
differ. Direction: neutral graphite surfaces, teal accent reserved for primary actions, selection
and live state, amber playhead as the only warm signal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tokens:
    name: str
    bg: str            # window / page
    sidebar: str       # second neutral layer: nav + status bar
    surface: str       # cards, tables
    surface2: str      # inputs, secondary buttons
    hover: str
    inset: str         # recessed areas: waveform, progress track
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str    # disabled / placeholder-level
    accent: str
    accent_hover: str
    accent_pressed: str
    on_accent: str
    accent_soft: str   # selection fill
    signal: str        # playhead
    ok: str
    warn: str
    err: str
    border_width: int = 1  # high-contrast uses thicker strokes


DARK = Tokens(
    name="dark",
    bg="#14161A", sidebar="#0F1114", surface="#1A1D22", surface2="#21252C", hover="#2A2F38", inset="#0D0F12",
    border="#262B33", border_strong="#3A414C",
    text="#E8EBF0", text_muted="#A0A8B4", text_faint="#6E7783",
    accent="#2DD4BF", accent_hover="#5EEAD4", accent_pressed="#14B8A6", on_accent="#04211E",
    accent_soft="rgba(45, 212, 191, 0.16)",
    signal="#F5A524", ok="#4ADE80", warn="#FBBF24", err="#F87171",
)

LIGHT = Tokens(
    name="light",
    bg="#F3F4F6", sidebar="#E9ECF0", surface="#FFFFFF", surface2="#F7F8FA", hover="#ECEFF3", inset="#E6E9ED",
    border="#DDE1E7", border_strong="#C3C9D2",
    text="#14181F", text_muted="#4B5563", text_faint="#8B94A1",
    accent="#0F766E", accent_hover="#115E59", accent_pressed="#134E4A", on_accent="#FFFFFF",
    accent_soft="rgba(15, 118, 110, 0.12)",
    signal="#B45309", ok="#15803D", warn="#A16207", err="#B91C1C",
)

HIGH_CONTRAST = Tokens(
    name="high_contrast",
    bg="#000000", sidebar="#000000", surface="#000000", surface2="#000000", hover="#1F1F1F", inset="#000000",
    border="#FFFFFF", border_strong="#FFFFFF",
    text="#FFFFFF", text_muted="#E5E5E5", text_faint="#A3A3A3",
    accent="#FFFF00", accent_hover="#FFFFFF", accent_pressed="#D4D400", on_accent="#000000",
    accent_soft="rgba(255, 255, 0, 0.25)",
    signal="#00FFFF", ok="#00FF66", warn="#FFD400", err="#FF6B6B",
    border_width=2,
)

_THEMES = {t.name: t for t in (DARK, LIGHT, HIGH_CONTRAST)}
_current: Tokens = DARK


def current_tokens() -> Tokens:
    """Tokens of the most recently built stylesheet (custom-painted widgets read colours from here)."""
    return _current


def _qss(t: Tokens) -> str:
    from app.ui.styles.icons import asset_path  # needs Qt; imported lazily so this module stays importable headless

    bw = t.border_width
    chev_down = asset_path("chevron-down", t.text_muted)
    chev_up = asset_path("chevron-up", t.text_muted)
    check = asset_path("check", t.on_accent, 12)
    return f"""
/* ---- Base ---- */
QWidget {{
    background-color: {t.bg};
    color: {t.text};
    font-size: 13px;
    selection-background-color: {t.accent};
    selection-color: {t.on_accent};
}}
QLabel {{ background: transparent; }}
QMainWindow, QDialog {{ background-color: {t.bg}; }}
QToolTip {{
    background-color: {t.surface2}; color: {t.text};
    border: {bw}px solid {t.border_strong}; padding: 4px 8px;
}}

/* ---- Type roles ---- */
#pageHeader {{ font-size: 20px; font-weight: 700; color: {t.text}; }}
#brandLabel {{ font-size: 15px; font-weight: 700; color: {t.text}; padding: 0; }}
#mutedText {{ color: {t.text_muted}; }}
#okText {{ color: {t.ok}; font-weight: 600; }}
#warnText {{ color: {t.warn}; font-weight: 600; }}
#errText {{ color: {t.err}; font-weight: 600; }}
#stepLabel {{ color: {t.accent}; font-size: 13px; font-weight: 700; }}
#scriptQuote {{
    color: {t.text}; font-style: italic; padding: 8px 10px;
    background-color: {t.surface2}; border-radius: 6px;
}}

/* ---- Sidebar ---- */
#sidebar {{
    background-color: {t.sidebar};
    border-right: 1px solid {t.border};
    min-width: 196px; max-width: 196px;
}}
#sidebar QWidget {{ background-color: transparent; }}
#sidebar QPushButton {{
    background-color: transparent; color: {t.text_muted};
    text-align: left; padding: 9px 12px; margin: 1px 8px;
    font-size: 13px; font-weight: 500;
    border: {bw}px solid transparent; border-radius: 8px;
}}
#sidebar QPushButton:hover {{ background-color: {t.hover}; color: {t.text}; }}
#sidebar QPushButton:focus {{ border-color: {t.accent}; }}
#sidebar QPushButton:checked {{
    background-color: {t.accent_soft}; color: {t.text}; font-weight: 600;
}}

/* ---- Buttons ---- */
QPushButton {{
    background-color: {t.surface2}; color: {t.text};
    border: {bw}px solid {t.border_strong}; border-radius: 7px;
    padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background-color: {t.hover}; }}
QPushButton:pressed {{ background-color: {t.inset}; }}
QPushButton:focus {{ border-color: {t.accent}; }}
QPushButton:disabled {{
    background-color: {t.surface}; color: {t.text_faint}; border-color: {t.border};
}}
QPushButton#primaryButton, QPushButton[accent="true"] {{
    background-color: {t.accent}; color: {t.on_accent};
    border: {bw}px solid {t.accent}; font-weight: 600;
}}
QPushButton#primaryButton {{ padding: 9px 18px; }}
QPushButton#primaryButton:hover, QPushButton[accent="true"]:hover {{
    background-color: {t.accent_hover}; border-color: {t.accent_hover};
}}
QPushButton#primaryButton:pressed, QPushButton[accent="true"]:pressed {{
    background-color: {t.accent_pressed}; border-color: {t.accent_pressed};
}}
QPushButton#primaryButton:disabled, QPushButton[accent="true"]:disabled {{
    background-color: {t.surface}; color: {t.text_faint}; border-color: {t.border};
}}
QPushButton#rowButton {{ padding: 3px 10px; }}
QPushButton[danger="true"] {{ color: {t.err}; }}
QPushButton[danger="true"]:disabled {{ color: {t.text_faint}; }}

/* ---- Inputs ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {t.surface2}; color: {t.text};
    border: {bw}px solid {t.border_strong}; border-radius: 7px; padding: 6px 10px;
}}
QPlainTextEdit, QTextEdit {{ padding: 10px 12px; background-color: {t.surface}; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ background-color: {t.hover}; }}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {t.accent};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    color: {t.text_faint}; background-color: {t.surface}; border-color: {t.border};
}}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 26px; border: none; background: transparent;
}}
QComboBox::down-arrow {{ image: url({chev_down}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background-color: {t.surface}; color: {t.text};
    border: {bw}px solid {t.border_strong}; padding: 4px; outline: 0;
    selection-background-color: {t.accent_soft}; selection-color: {t.text};
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 20px; border: none; background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 20px; border: none; background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({chev_up}); width: 9px; height: 9px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({chev_down}); width: 9px; height: 9px; }}

QCheckBox {{ spacing: 8px; background: transparent; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: {bw}px solid {t.border_strong}; background-color: {t.surface2};
}}
QCheckBox::indicator:hover {{ border-color: {t.accent}; }}
QCheckBox::indicator:checked {{ background-color: {t.accent}; border-color: {t.accent}; image: url({check}); }}
QCheckBox::indicator:disabled {{ background-color: {t.surface}; border-color: {t.border}; }}
QCheckBox:disabled {{ color: {t.text_faint}; }}

/* ---- Slider ---- */
QSlider::groove:horizontal {{ height: 4px; background: {t.border_strong}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 12px; height: 12px; margin: -6px 0; border-radius: 8px;
    background: {t.accent}; border: 2px solid {t.surface};
}}
QSlider::handle:horizontal:hover {{ background: {t.accent_hover}; }}

/* ---- Progress ---- */
QProgressBar {{
    background-color: {t.inset}; border: {bw}px solid {t.border}; border-radius: 6px;
    text-align: center; color: {t.text_muted}; font-size: 11px; min-height: 16px;
}}
QProgressBar::chunk {{ background-color: {t.accent}; border-radius: 5px; }}
QProgressBar#slimProgress {{ min-height: 6px; max-height: 6px; border: none; border-radius: 3px; }}
QProgressBar#slimProgress::chunk {{ border-radius: 3px; }}

/* ---- Cards ---- */
QGroupBox {{
    background-color: {t.surface}; border: {bw}px solid {t.border}; border-radius: 10px;
    margin-top: 0; padding: 38px 14px 14px 14px;
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left;
    left: 14px; top: 12px; color: {t.text}; font-size: 13px; font-weight: 700;
    background: transparent;
}}
#cell {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}

/* ---- Tables ---- */
QTableWidget {{
    background-color: {t.surface}; alternate-background-color: {t.surface2};
    border: {bw}px solid {t.border}; border-radius: 10px;
    gridline-color: transparent; outline: 0;
}}
QTableWidget::item {{ padding: 4px 10px; border: none; }}
QTableWidget::item:selected {{ background-color: {t.accent_soft}; color: {t.text}; }}
QHeaderView {{ background-color: {t.surface}; }}
QHeaderView::section {{
    background-color: {t.surface}; color: {t.text_muted};
    padding: 8px 10px; border: none; border-bottom: {bw}px solid {t.border_strong};
    font-size: 12px; font-weight: 600;
}}
QTableCornerButton::section {{ background-color: {t.surface}; border: none; }}

/* ---- Scrollbars ---- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.border_strong}; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:horizontal {{ background: {t.border_strong}; border-radius: 4px; min-width: 32px; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {t.text_faint}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- Status bar & menus ---- */
QStatusBar {{
    background-color: {t.sidebar}; color: {t.text_muted};
    border-top: 1px solid {t.border}; font-size: 12px;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ padding: 0 8px; background: transparent; color: {t.text_muted}; }}
QMenu {{ background-color: {t.surface}; border: {bw}px solid {t.border_strong}; padding: 4px; }}
QMenu::item {{ padding: 6px 20px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {t.accent_soft}; }}
"""


def get_theme_stylesheet(theme_name: str = "dark") -> str:
    """Builds the QSS for the requested theme and records its tokens for custom-painted widgets."""
    global _current
    _current = _THEMES.get(theme_name.lower().strip(), DARK)
    return _qss(_current)


def configure_table(table) -> None:
    """Shared table behaviour: no row numbers or grid lines, zebra rows, roomy 44px rows."""
    from PySide6.QtCore import Qt  # type: ignore
    from PySide6.QtWidgets import QAbstractItemView  # type: ignore

    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(44)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)


def status_color(kind: str) -> str:
    """Hex colour for a status ("ok", "warn", "err", "muted") in the active theme."""
    t = _current
    return {"ok": t.ok, "warn": t.warn, "err": t.err, "muted": t.text_muted}[kind]


def status_brush(kind: str):
    """QBrush for a table-cell status colour in the active theme."""
    from PySide6.QtGui import QBrush, QColor  # type: ignore

    return QBrush(QColor(status_color(kind)))
