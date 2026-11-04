#!/usr/bin/env bash
# Build script for VoiceClone Studio on Linux (PyInstaller / AppImage)
set -e

echo "=== Building VoiceClone Studio for Linux ==="

# 1. Check requirements
python3 -m pip install --upgrade pip
python3 -m pip install -r voiceclone/requirements.txt pyinstaller

# 2. Run PyInstaller
echo "Running PyInstaller..."
pyinstaller --noconfirm --log-level=WARN \
    --name="VoiceCloneStudio" \
    --windowed \
    --add-data="voiceclone/app/ui/styles:voiceclone/app/ui/styles" \
    --hidden-import="PySide6.QtCore" \
    --hidden-import="PySide6.QtGui" \
    --hidden-import="PySide6.QtWidgets" \
    --hidden-import="platformdirs" \
    --hidden-import="soundfile" \
    --hidden-import="sounddevice" \
    --hidden-import="pyloudnorm" \
    --hidden-import="noisereduce" \
    voiceclone/main.py

echo "Build complete! Binary located in dist/VoiceCloneStudio/"

