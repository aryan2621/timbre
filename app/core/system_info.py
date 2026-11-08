from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil

from app.core.device import device_manager

OS_RESERVE_FRACTION = 0.20
OS_RESERVE_MIN_GB = 3.0
APP_RESERVE_GB = 2.0
GPU_DISPLAY_RESERVE_GB = 1.0
GIB = 1024**3


@dataclass(frozen=True)
class SystemSpecs:
    os_name: str
    cpu_name: str
    cpu_cores: int
    ram_gb: float
    accelerator: str
    accelerator_name: str
    memory_budget_gb: float
    memory_reserved_gb: float
    disk_free_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def memory_label(self) -> str:
        return "GPU memory" if self.accelerator == "cuda" else "memory"


def _cpu_name() -> str:
    try:
        if platform.system() == "Darwin":
            return subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            ).stdout.strip()
        if platform.system() == "Linux":
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.processor() or platform.machine() or "Unknown CPU"


def _disk_free_bytes(directory: Path) -> int:
    probe = directory
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _memory_budget_gb(accelerator: str, ram_gb: float, vram_gb: float) -> tuple[float, float]:
    if accelerator == "cuda" and vram_gb:
        return max(vram_gb - GPU_DISPLAY_RESERVE_GB, 0.0), GPU_DISPLAY_RESERVE_GB
    reserved = max(ram_gb * OS_RESERVE_FRACTION, OS_RESERVE_MIN_GB) + APP_RESERVE_GB
    return max(ram_gb - reserved, 0.0), reserved


def get_system_specs(models_dir: Path) -> SystemSpecs:
    ram_gb = psutil.virtual_memory().total / GIB
    device = device_manager.get_device_info()
    budget, reserved = _memory_budget_gb(device.device_type, ram_gb, device.total_memory_mb / 1024)
    return SystemSpecs(
        os_name=f"{platform.system()} {platform.release()}",
        cpu_name=_cpu_name(),
        cpu_cores=psutil.cpu_count(logical=False) or psutil.cpu_count() or 1,
        ram_gb=round(ram_gb, 1),
        accelerator=device.device_type,
        accelerator_name=device.device_name,
        memory_budget_gb=round(budget, 1),
        memory_reserved_gb=round(reserved, 1),
        disk_free_bytes=_disk_free_bytes(models_dir),
    )
