"""
Hardware detection and execution device management (CUDA, Apple MPS, CPU).
Provides VRAM queries, torch memory cache clearing, and OOM diagnostic messaging.
"""

from __future__ import annotations

import platform
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
    allocated_memory_mb: float = 0.0
    free_memory_mb: float = 0.0
    supports_fp16: bool = False
    supports_bf16: bool = False
    warning_message: str | None = None


class DeviceManager:
    """Detects available hardware acceleration and configures PyTorch devices."""

    def __init__(self) -> None:
        self._torch_available: bool = False
        self._torch: Any = None
        self._check_torch()

    def _check_torch(self) -> None:
        try:
            import torch  # type: ignore
            self._torch = torch
            self._torch_available = True
        except ImportError:
            self._torch_available = False
            logger.warning("PyTorch is not installed in the current environment. Defaulting to CPU mock.")

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
                allocated_mem = torch.cuda.memory_allocated(device_index) / (1024 * 1024)
                reserved_mem = torch.cuda.memory_reserved(device_index) / (1024 * 1024)
                free_mem = total_mem - reserved_mem

                # Capability check for half precision
                major, minor = props.major, props.minor
                supports_fp16 = major >= 6 or (major == 5 and minor >= 3)
                supports_bf16 = major >= 8

                return DeviceInfo(
                    device_type="cuda",
                    device_name=f"{props.name} (CUDA {major}.{minor})",
                    total_memory_mb=round(total_mem, 1),
                    allocated_memory_mb=round(allocated_mem, 1),
                    free_memory_mb=round(max(0.0, free_mem), 1),
                    supports_fp16=supports_fp16,
                    supports_bf16=supports_bf16,
                )
            except Exception as e:
                logger.error("Failed to query CUDA device properties: %s", e)
                return DeviceInfo(
                    device_type="cuda",
                    device_name="NVIDIA GPU (CUDA)",
                    supports_fp16=True,
                )

        if target == "mps" and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return DeviceInfo(
                device_type="mps",
                device_name=f"Apple Silicon GPU (MPS / {platform.machine()})",
                total_memory_mb=0.0,  # Unified memory on Apple Silicon
                supports_fp16=True,
                supports_bf16=False,
            )

        # CPU Fallback
        cpu_name = platform.processor() or platform.machine() or "Generic CPU"
        return DeviceInfo(
            device_type="cpu",
            device_name=f"CPU ({cpu_name})",
            supports_fp16=False,
            supports_bf16=False,
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

