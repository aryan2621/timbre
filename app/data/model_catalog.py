"""
Catalog of supported neural TTS models and local presence checks.

Shared by the desktop UI and the HTTP sidecar so both report the same
licenses, sizes and download locations.

Each catalog entry may list ``files`` — every file the engine needs. LFS files
carry a SHA-256 that is verified after download; non-LFS files (small JSON
assets) are size-checked only. ``is_model_present`` treats an entry as
downloaded only when every listed file is present (no ``.part`` files).
"""

from __future__ import annotations

from pathlib import Path

from app.data.models import ModelFile, ModelMetadata

_CHATTERBOX = "https://huggingface.co/ResembleAI/chatterbox/resolve/main"
_XTTS = "https://huggingface.co/coqui/XTTS-v2/resolve/main"
_F5 = "https://huggingface.co/SWivid/F5-TTS/resolve/main/F5TTS_Base"

CATALOG_MODELS: list[ModelMetadata] = [
    ModelMetadata(
        id="chatterbox-tts",
        name="Chatterbox TTS",
        version="1.2.0",
        license_name="MIT License (Commercial Allowed)",
        commercial_allowed=True,
        license_notice="Open-source zero-shot voice cloner with Perth watermarking. Multilingual (23 languages including Hindi).",
        download_url=f"{_CHATTERBOX}/ve.safetensors",
        expected_sha256="",
        total_bytes=6_400_811_366,  # EN (5 files) + MTL (5 files)
        local_dir="chatterbox",
        min_ram_gb=8,
        recommended=True,
        files=[
            # --- English model (from_local) ---
            ModelFile("ve.safetensors", f"{_CHATTERBOX}/ve.safetensors", 5_695_784,
                      "f0921cab452fa278bc25cd23ffd59d36f816d7dc5181dd1bef9751a7fb61f63c"),
            ModelFile("t3_cfg.safetensors", f"{_CHATTERBOX}/t3_cfg.safetensors", 2_129_653_744,
                      "914cb1696f47527fe8852ca8f1fe1fa63cb34f76f9c715e84e067b744dd0da81"),
            ModelFile("s3gen.safetensors", f"{_CHATTERBOX}/s3gen.safetensors", 1_056_484_620,
                      "2b78103c654207393955e4900aac14a12de8ef25f4b09424f1ef91941f161d4e"),
            ModelFile("tokenizer.json", f"{_CHATTERBOX}/tokenizer.json", 25_470, ""),
            ModelFile("conds.pt", f"{_CHATTERBOX}/conds.pt", 107_374,
                      "6552d70568833628ba019c6b03459e77fe71ca197d5c560cef9411bee9d87f4e"),
            # --- Multilingual model (from_local, 23 languages incl. Hindi) ---
            ModelFile("ve.pt", f"{_CHATTERBOX}/ve.pt", 5_698_626,
                      "4b16d836bc598509860f6fa068165a8bb5e9ac84f05582dfcf278a5a372879f1"),
            ModelFile("t3_mtl23ls_v2.safetensors", f"{_CHATTERBOX}/t3_mtl23ls_v2.safetensors", 2_143_989_752,
                      "b1237586127ce98e7800a68e49938eb5092846862aabcb6e17b2fda7889a6c75"),
            ModelFile("s3gen.pt", f"{_CHATTERBOX}/s3gen.pt", 1_057_165_844,
                      "9b9ff07e60b20c136e2b1b3d7563a24604e8d2c4c267888d1ee929dd0151d2a3"),
            ModelFile("grapheme_mtl_merged_expanded_v1.json", f"{_CHATTERBOX}/grapheme_mtl_merged_expanded_v1.json", 69_989, ""),
            ModelFile("Cangjie5_TC.json", f"{_CHATTERBOX}/Cangjie5_TC.json", 1_920_163, ""),
        ],
    ),
    ModelMetadata(
        id="xtts-v2",
        name="Coqui XTTS v2",
        version="2.0.3",
        license_name="CPML (Strictly Non-Commercial)",
        commercial_allowed=False,
        license_notice="Multi-lingual voice cloner. Commercial use is strictly prohibited by CPML.",
        download_url=f"{_XTTS}/model.pth",
        expected_sha256="c7ea20001c6a0a841c77e252d8409f6a74fb423e79b3206a0771ba5989776187",
        total_bytes=1_867_929_118,
        local_dir="xtts_v2",
        min_ram_gb=12,
        files=[
            ModelFile("model.pth", f"{_XTTS}/model.pth", 1_867_929_118,
                      "c7ea20001c6a0a841c77e252d8409f6a74fb423e79b3206a0771ba5989776187"),
        ],
    ),
    ModelMetadata(
        id="f5-tts",
        name="F5-TTS",
        version="1.0.0",
        license_name="MIT License (Commercial Allowed)",
        commercial_allowed=True,
        license_notice="Diffusion transformer zero-shot cloner with Flow Matching.",
        download_url=f"{_F5}/model_1200000.safetensors",
        expected_sha256="4180310f91d592cee4bc14998cd37c781f779cf105e8ca8744d9bd48ca7046ae",
        total_bytes=1_348_645_281,
        local_dir="f5_tts",
        min_ram_gb=6,
        files=[
            ModelFile("model_1200000.safetensors", f"{_F5}/model_1200000.safetensors", 1_348_645_281,
                      "4180310f91d592cee4bc14998cd37c781f779cf105e8ca8744d9bd48ca7046ae"),
        ],
    ),
]


def model_local_path(model: ModelMetadata, models_dir: Path) -> Path:
    """Directory where a model's weights are stored."""
    return models_dir / model.local_dir


def is_model_present(model: ModelMetadata, models_dir: Path) -> bool:
    """True when every listed file exists (``.part`` files never count)."""
    model_path = model_local_path(model, models_dir)
    if not model_path.exists():
        return False
    return all((model_path / f.name).is_file() for f in model.files)


def get_model(model_id: str) -> ModelMetadata | None:
    """Looks up a catalog model by its stable id."""
    return next((model for model in CATALOG_MODELS if model.id == model_id), None)
