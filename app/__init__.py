"""
VoiceClone Studio — Production-quality local zero-shot voice cloning desktop application.
"""

import sys

__version__ = "1.0.0"
__author__ = "VoiceClone Engineering Team"

# Expose as voiceclone.app alias for external consumers
sys.modules["voiceclone.app"] = sys.modules[__name__]
