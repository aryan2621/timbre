"""Local shadow of the broken upstream PySide6 stub package.

The PySide6 wheels ship a QtGui.pyi with invalid indentation, which mypy
refuses to parse. The application already guards every Qt import with a
try/except ImportError fallback, so the Qt surface is typed as Any here.
"""

from typing import Any

__path__: list[str]
