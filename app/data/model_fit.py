from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.core.system_info import GIB, SystemSpecs
from app.data.models import ModelMetadata

RECOMMENDED = "recommended"
POSSIBLE = "possible"
BLOCKED = "blocked"

DISK_HEADROOM = 1.1
COMFORT_FACTOR = 1.5


@dataclass(frozen=True)
class ModelFit:
    status: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def assess_fit(model: ModelMetadata, specs: SystemSpecs, installed: bool) -> ModelFit:
    blockers: list[str] = []
    needed_disk = int(model.total_bytes * DISK_HEADROOM)
    if not installed and specs.disk_free_bytes < needed_disk:
        blockers.append(
            f"Needs {needed_disk / GIB:.1f} GB of free disk, "
            f"{specs.disk_free_bytes / GIB:.1f} GB available."
        )
    if specs.memory_budget_gb < model.min_memory_gb:
        blockers.append(
            f"Needs about {model.min_memory_gb:g} GB of {specs.memory_label}, "
            f"this machine can offer {specs.memory_budget_gb:g} GB after leaving "
            f"{specs.memory_reserved_gb:g} GB for the system and this app."
        )
    if blockers:
        return ModelFit(BLOCKED, blockers)

    cautions: list[str] = []
    if model.gpu_recommended and specs.accelerator == "cpu":
        cautions.append("No GPU detected. It will run, but slowly.")
    if specs.memory_budget_gb < model.min_memory_gb * COMFORT_FACTOR:
        cautions.append(f"Close to this machine's {specs.memory_label} limit.")
    return ModelFit(POSSIBLE if cautions else RECOMMENDED, cautions)
