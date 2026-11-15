"""
Hardware detection and execution device management (CUDA, Apple MPS, CPU).
Provides VRAM queries, torch memory cache clearing, and OOM diagnostic messaging.
"""

from __future__ import annotations

import platform
import threading
from dataclasses import dataclass
from typing import Any

from app.core.logging_setup import get_logger

logger = get_logger("device")


@dataclass
class DeviceInfo:
    """Detailed summary of the detected compute hardware."""

    device_type: str  # "cuda", "mps", "cpu"
    device_name: str
    total_memory_mb: float = 0.0
    warning_message: str | None = None


class DeviceManager:
    """Detects available hardware acceleration and configures PyTorch devices."""

    def __init__(self) -> None:
        self._module: Any = None
        self._probed = False
        self._probe_lock = threading.Lock()

    @property
    def _torch(self) -> Any:
        """torch, imported on first use so the API can start listening before the multi-second import."""
        if not self._probed:
            with self._probe_lock:  # a second caller waits for the import instead of seeing None
                if not self._probed:
                    try:
                        import torch  # type: ignore

                        self._module = torch
                    except ImportError:
                        logger.warning("PyTorch is not installed in the current environment. Defaulting to CPU mock.")
                    self._probed = True
        return self._module

    @property
    def probed(self) -> bool:
        """True once torch has been imported (or found missing); health uses it to avoid forcing the import."""
        return self._probed

    @property
    def _torch_available(self) -> bool:
        return self._torch is not None

    def get_preferred_device(self, preference: str = "auto") -> str:
        """
        Determines the optimal device string ('cuda', 'cuda:0', 'mps', or 'cpu')
        based on hardware availability and user preference.
        """
        if not self._torch_available or self._torch is None:
            return "cpu"

        torch = self._torch

        if preference == "cuda":
            if torch.cuda.is_available():
                return "cuda"
            logger.warning("CUDA requested but not available. Falling back to auto.")

        elif preference == "mps":
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            logger.warning("Apple MPS requested but not available. Falling back to auto.")

        elif preference == "cpu":
            return "cpu"

        # Auto detection logic
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"

        return "cpu"

    def get_device_info(self, active_device_str: str | None = None) -> DeviceInfo:
        """Inspects the system and returns detailed metrics about the selected or active device."""
        if not self._torch_available or self._torch is None:
            return DeviceInfo(
                device_type="cpu",
                device_name=f"Host CPU ({platform.processor() or 'Standard'})",
                total_memory_mb=0.0,
                warning_message="PyTorch not detected. Running in CPU compatibility mode.",
            )

        torch = self._torch
        target = active_device_str or self.get_preferred_device("auto")

        if target.startswith("cuda") and torch.cuda.is_available():
            try:
                device_index = torch.cuda.current_device()
                props = torch.cuda.get_device_properties(device_index)
                total_mem = props.total_memory / (1024 * 1024)
                major, minor = props.major, props.minor

                return DeviceInfo(
                    device_type="cuda",
                    device_name=f"{props.name} (CUDA {major}.{minor})",
                    total_memory_mb=round(total_mem, 1),
                )
            except Exception as e:
                logger.error("Failed to query CUDA device properties: %s", e)
                return DeviceInfo(
                    device_type="cuda",
                    device_name="NVIDIA GPU (CUDA)",
                )

        if target == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return DeviceInfo(
                device_type="mps",
                device_name=f"Apple Silicon GPU (MPS / {platform.machine()})",
                total_memory_mb=0.0,  # Unified memory on Apple Silicon
            )

        # CPU Fallback
        cpu_name = platform.processor() or platform.machine() or "Generic CPU"
        return DeviceInfo(
            device_type="cpu",
            device_name=f"CPU ({cpu_name})",
            warning_message="Running on CPU. Synthesis will be slower than with GPU acceleration.",
        )

    def clear_cache(self) -> None:
        """Frees cached allocations in CUDA or MPS memory."""
        if not self._torch_available or self._torch is None:
            return

        torch = self._torch
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
            logger.debug("Hardware device cache successfully purged.")
        except Exception as e:
            logger.warning("Error clearing device cache: %s", e)

    @staticmethod
    def format_oom_message(error: Exception) -> str:
        """Constructs an actionable, user-friendly error explanation when an Out Of Memory condition occurs."""
        return (
            "Out of Memory (OOM) Error Detected during speech synthesis.\n\n"
            "Suggested Fixes:\n"
            "1. Reduce the text length or enable sentence chunking in Studio settings.\n"
            "2. Close other heavy applications utilizing GPU or system memory.\n"
            "3. Go to Settings -> Device and enable 'Half Precision (fp16)'.\n"
            "4. If running on a GPU with < 6GB VRAM, switch the Device preference to 'CPU' in Settings.\n\n"
            f"Technical Details: {str(error)}"
        )


device_manager = DeviceManager()

