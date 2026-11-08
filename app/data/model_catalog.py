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
_ACE_STEP = "https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF/resolve/main"
_STABLE_AUDIO = "https://huggingface.co/stabilityai/stable-audio-open-1.0/resolve/main"
_POCKET = "https://huggingface.co/kyutai/pocket-tts/resolve/db04f0e653473e5c7333c69686ac92b7460b0c1d/languages/english_2026-10"
_POCKET_TOKENIZER = "https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/resolve/00eac05ed3d16bdc3f6b5d598874019c34a89214/languages/english_2026-09"
_AUDIOLDM = "https://huggingface.co/cvssp/audioldm-s-full-v2/resolve/main"
_MUSICGEN = "https://huggingface.co/facebook/musicgen-small/resolve/main"
_QWEN = "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main"
_WHISPER = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"

CATALOG_MODELS: list[ModelMetadata] = [
    ModelMetadata(
        id="pocket-tts",
        name="Pocket TTS",
        version="2026-10",
        license_name="CC BY 4.0 (attribution required)",
        commercial_allowed=True,
        license_notice="Kyutai's 100M-parameter voice cloner. About 10x faster than real time on a laptop CPU, English. Gated on Hugging Face: accept the terms on the model page and add your own access token before downloading.",
        total_bytes=219_274_216,
        local_dir="pocket-tts",
        gated_url="https://huggingface.co/kyutai/pocket-tts",
        category="voice-cloning",
        min_memory_gb=2.0,
        files=[
            ModelFile("model.safetensors", f"{_POCKET}/model.safetensors", 219_029_196, ""),
            ModelFile("tokenizer.json", f"{_POCKET_TOKENIZER}/tokenizer.json", 245_020, ""),
        ],
    ),
    ModelMetadata(
        id="chatterbox-tts",
        name="Chatterbox TTS",
        version="1.2.0",
        license_name="MIT License (Commercial Allowed)",
        commercial_allowed=True,
        license_notice="Open-source zero-shot voice cloner with Perth watermarking. Multilingual (23 languages including Hindi).",
        total_bytes=6_400_811_366,  # EN (5 files) + MTL (5 files)
        local_dir="chatterbox",
        category="voice-cloning",
        min_memory_gb=8.0,
        gpu_recommended=True,
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
        id="stable-audio-open",
        name="Stable Audio Open 1.0",
        version="1.0",
        license_name="Stability AI Community License (free under $1M revenue)",
        commercial_allowed=True,
        license_notice="Text-to-audio for sound effects and short music, up to 47 seconds, stereo 44.1 kHz. Gated on Hugging Face: accept the licence on the model page and add your own access token on the Models page before downloading.",
        total_bytes=5_295_649_370,
        local_dir="stable-audio-open",
        gated_url="https://huggingface.co/stabilityai/stable-audio-open-1.0",
        category="sound",
        min_memory_gb=8.0,
        gpu_recommended=True,
        files=[
            ModelFile("model_index.json", f"{_STABLE_AUDIO}/model_index.json", 498, ""),
            ModelFile("projection_model/config.json", f"{_STABLE_AUDIO}/projection_model/config.json", 181, ""),
            ModelFile("projection_model/diffusion_pytorch_model.safetensors", f"{_STABLE_AUDIO}/projection_model/diffusion_pytorch_model.safetensors", 1_586_944, "032102e2b0e4b9b9e19c648dc476345157b97906752a7b4b7a0133900f340926"),
            ModelFile("scheduler/scheduler_config.json", f"{_STABLE_AUDIO}/scheduler/scheduler_config.json", 411, ""),
            ModelFile("text_encoder/config.json", f"{_STABLE_AUDIO}/text_encoder/config.json", 1_497, ""),
            ModelFile("text_encoder/model.safetensors", f"{_STABLE_AUDIO}/text_encoder/model.safetensors", 438_525_864, "095878c81d21f17d235e1b4aa20e9595289177e2658ef4dcec69fa5aa3b07ca2"),
            ModelFile("tokenizer/special_tokens_map.json", f"{_STABLE_AUDIO}/tokenizer/special_tokens_map.json", 2_201, ""),
            ModelFile("tokenizer/spiece.model", f"{_STABLE_AUDIO}/tokenizer/spiece.model", 791_656, "d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86"),
            ModelFile("tokenizer/tokenizer.json", f"{_STABLE_AUDIO}/tokenizer/tokenizer.json", 2_422_169, ""),
            ModelFile("tokenizer/tokenizer_config.json", f"{_STABLE_AUDIO}/tokenizer/tokenizer_config.json", 20_768, ""),
            ModelFile("transformer/config.json", f"{_STABLE_AUDIO}/transformer/config.json", 391, ""),
            ModelFile("transformer/diffusion_pytorch_model.safetensors", f"{_STABLE_AUDIO}/transformer/diffusion_pytorch_model.safetensors", 4_227_806_200, "65ae9715febfeb2dc9f33aa506c2bda69fd2ddf8ebc483fb2df090df4ca506fd"),
            ModelFile("vae/config.json", f"{_STABLE_AUDIO}/vae/config.json", 350, ""),
            ModelFile("vae/diffusion_pytorch_model.safetensors", f"{_STABLE_AUDIO}/vae/diffusion_pytorch_model.safetensors", 624_490_240, "2131cdb52020b2473707465449d8bdb4f6cca61c93150a947baca02bc58ffd7b"),
        ],
    ),
    ModelMetadata(
        id="ace-step",
        name="ACE-Step 1.5",
        version="1.5",
        license_name="Apache-2.0",
        commercial_allowed=True,
        license_notice="Songs with optional lyrics, up to ten minutes. Runs on the bundled native server, nothing else to install.",
        total_bytes=5_646_931_456,
        local_dir="ace-step",
        category="music",
        min_memory_gb=6.0,
        gpu_recommended=True,
        files=[
            ModelFile("acestep-5Hz-lm-1.7B-Q8_0.gguf", f"{_ACE_STEP}/acestep-5Hz-lm-1.7B-Q8_0.gguf", 1_975_837_568,
                      "726f99a82f050b32ebc5c5e36acaa9d7acd06bfe5e579a62b00e0d0d6d0b7ec6"),
            ModelFile("Qwen3-Embedding-0.6B-Q8_0.gguf", f"{_ACE_STEP}/Qwen3-Embedding-0.6B-Q8_0.gguf", 784_144_960,
                      "972f23255e46adfe744a0eb9a0039f3c63988f65753b0968d776e8b27168c321"),
            ModelFile("acestep-v15-turbo-Q8_0.gguf", f"{_ACE_STEP}/acestep-v15-turbo-Q8_0.gguf", 2_549_528_000,
                      "288f708a61cfc241013a98a62f98ba331f83fe34d0d3559acdd9b0f6a2f7cd6b"),
            ModelFile("vae-BF16.gguf", f"{_ACE_STEP}/vae-BF16.gguf", 337_420_928,
                      "0599862ac5d15cd308e1d2e368373aea6c02e25ebd1737ad4a4562a0901b0ef8"),
        ],
    ),
    ModelMetadata(
        id="agent-llm",
        name="Qwen3 4B Instruct",
        version="2507",
        license_name="Apache-2.0",
        commercial_allowed=True,
        license_notice="The language model behind voice agents. Runs on the bundled llama.cpp server, nothing else to install.",
        total_bytes=2_497_281_120,
        local_dir="agent-llm",
        category="voice-agent",
        min_memory_gb=6.0,
        gpu_recommended=True,
        files=[
            ModelFile("Qwen3-4B-Instruct-2507-Q4_K_M.gguf", f"{_QWEN}/Qwen3-4B-Instruct-2507-Q4_K_M.gguf", 2_497_281_120,
                      "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"),
        ],
    ),
    ModelMetadata(
        id="agent-llm-qwen3-1-7b",
        name="Qwen3 1.7B",
        version="3",
        license_name="Apache-2.0",
        commercial_allowed=True,
        license_notice="Smallest and quickest. Good for short replies on modest hardware. Runs on the bundled llama.cpp server.",
        total_bytes=1107409472,
        local_dir="agent-llm-qwen3-1-7b",
        category="voice-agent",
        min_memory_gb=2.0,
        gpu_recommended=True,
        files=[
            ModelFile("Qwen3-1.7B-Q4_K_M.gguf", "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf", 1107409472,
                      "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897"),
        ],
    ),
    ModelMetadata(
        id="agent-llm-gemma-3-4b",
        name="Gemma 3 4B",
        version="3",
        license_name="Gemma Terms of Use",
        commercial_allowed=True,
        license_notice="Google's multilingual chat model. Use is subject to Google's Gemma terms. Runs on the bundled llama.cpp server.",
        total_bytes=2489894016,
        local_dir="agent-llm-gemma-3-4b",
        category="voice-agent",
        min_memory_gb=5.0,
        gpu_recommended=True,
        files=[
            ModelFile("gemma-3-4b-it-Q4_K_M.gguf", "https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf", 2489894016,
                      "04a43a22e8d2003deda5acc262f68ec1005fa76c735a9962a8c77042a74a7d19"),
        ],
    ),
    ModelMetadata(
        id="agent-llm-qwen3-8b",
        name="Qwen3 8B",
        version="3",
        license_name="Apache-2.0",
        commercial_allowed=True,
        license_notice="Larger and smarter. Needs about 9 GB of free memory. Runs on the bundled llama.cpp server.",
        total_bytes=5027784512,
        local_dir="agent-llm-qwen3-8b",
        category="voice-agent",
        min_memory_gb=9.0,
        gpu_recommended=True,
        files=[
            ModelFile("Qwen3-8B-Q4_K_M.gguf", "https://huggingface.co/unsloth/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf", 5027784512,
                      "120307ba529eb2439d6c430d94104dabd578497bc7bfe7e322b5d9933b449bd4"),
        ],
    ),
    ModelMetadata(
        id="agent-whisper",
        name="Whisper base (English)",
        version="1.0",
        license_name="MIT License",
        commercial_allowed=True,
        license_notice="Listens for voice agents. Runs on the bundled whisper.cpp server.",
        total_bytes=147_964_211,
        local_dir="agent-whisper",
        category="voice-agent",
        min_memory_gb=2.0,
        files=[
            ModelFile("ggml-base.en.bin", f"{_WHISPER}/ggml-base.en.bin", 147_964_211,
                      "a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002"),
        ],
    ),
    ModelMetadata(
        id="agent-whisper-large-v3-turbo",
        name="Whisper large v3 turbo (multilingual)",
        version="1.0",
        license_name="MIT License",
        commercial_allowed=True,
        license_notice="Best accuracy and 99 languages. Used automatically when installed. Listens for voice agents on the bundled whisper.cpp server.",
        total_bytes=574041195,
        local_dir="agent-whisper-large-v3-turbo",
        category="voice-agent",
        min_memory_gb=3.0,
        files=[
            ModelFile("ggml-large-v3-turbo-q5_0.bin", f"{_WHISPER}/ggml-large-v3-turbo-q5_0.bin", 574041195,
                      "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"),
        ],
    ),
    ModelMetadata(
        id="agent-llm-llama-3-1-8b",
        name="Llama 3.1 8B",
        version="3.1",
        license_name="Llama 3.1 Community License",
        commercial_allowed=True,
        license_notice="Strong general model with solid tool use. Use is subject to Meta's licence. Runs on the bundled llama.cpp server.",
        total_bytes=4920739200,
        local_dir="agent-llm-llama-3-1-8b",
        category="voice-agent",
        min_memory_gb=8.0,
        gpu_recommended=True,
        files=[
            ModelFile("Llama-3.1-8B-Instruct-Q4_K_M.gguf", "https://huggingface.co/unsloth/Llama-3.1-8B-Instruct-GGUF/resolve/main/Llama-3.1-8B-Instruct-Q4_K_M.gguf", 4920739200,
                      "b3bdbf23b47d7e6bb791c99b206deb169cd5a96362a9e3399028df2faacdc506"),
        ],
    ),
    ModelMetadata(
        id="audioldm-s",
        name="AudioLDM",
        version="s-full-v2",
        license_name="CC BY-NC-SA 4.0",
        commercial_allowed=False,
        license_notice="Quick sound effects from a text description, up to 40 seconds. Non-commercial use only.",
        total_bytes=1687448107,
        local_dir="audioldm-s",
        category="sound",
        min_memory_gb=4.0,
        gpu_recommended=True,
        files=[
            ModelFile("model_index.json", f"{_AUDIOLDM}/model_index.json", 462, ""),
            ModelFile("scheduler/scheduler_config.json", f"{_AUDIOLDM}/scheduler/scheduler_config.json", 439, ""),
            ModelFile("text_encoder/config.json", f"{_AUDIOLDM}/text_encoder/config.json", 843, ""),
            ModelFile("text_encoder/model.safetensors", f"{_AUDIOLDM}/text_encoder/model.safetensors", 501241456, "c92b5a2bee69ff5dd05820d9e0a5cddbc9c9b9dd19a6cb3214f0cf4f29a4d1b0"),
            ModelFile("tokenizer/merges.txt", f"{_AUDIOLDM}/tokenizer/merges.txt", 456356, ""),
            ModelFile("tokenizer/special_tokens_map.json", f"{_AUDIOLDM}/tokenizer/special_tokens_map.json", 280, ""),
            ModelFile("tokenizer/tokenizer.json", f"{_AUDIOLDM}/tokenizer/tokenizer.json", 2108746, ""),
            ModelFile("tokenizer/tokenizer_config.json", f"{_AUDIOLDM}/tokenizer/tokenizer_config.json", 424, ""),
            ModelFile("tokenizer/vocab.json", f"{_AUDIOLDM}/tokenizer/vocab.json", 798293, ""),
            ModelFile("unet/config.json", f"{_AUDIOLDM}/unet/config.json", 1300, ""),
            ModelFile("unet/diffusion_pytorch_model.safetensors", f"{_AUDIOLDM}/unet/diffusion_pytorch_model.safetensors", 740228912, "fc30d5b5a3bb8d08672736efb1fff10755ba7024dace39b2dcb579a105aa2a5a"),
            ModelFile("vae/config.json", f"{_AUDIOLDM}/vae/config.json", 534, ""),
            ModelFile("vae/diffusion_pytorch_model.safetensors", f"{_AUDIOLDM}/vae/diffusion_pytorch_model.safetensors", 221530316, "42f64f7565b23eabde68c9694e39f18b8bba5f7a14f477e7ed4b51e0ea7de8a5"),
            ModelFile("vocoder/config.json", f"{_AUDIOLDM}/vocoder/config.json", 654, ""),
            ModelFile("vocoder/model.safetensors", f"{_AUDIOLDM}/vocoder/model.safetensors", 221079092, "d9dc6513c30a5b86c2497712690c04fe74b4aa79fdab6d490b34fcb4e24c590c"),
        ],
    ),
    ModelMetadata(
        id="musicgen-small",
        name="MusicGen small",
        version="1.0",
        license_name="CC BY-NC 4.0",
        commercial_allowed=False,
        license_notice="Short instrumental music clips from a text description, up to 40 seconds. Non-commercial use only.",
        total_bytes=2603655906,
        local_dir="musicgen-small",
        category="music",
        min_memory_gb=4.0,
        gpu_recommended=True,
        files=[
            ModelFile("compression_state_dict.bin", f"{_MUSICGEN}/compression_state_dict.bin", 236001935, "37d256b525d4117f8bbf790ab448a8e9f4746cd401900fe1ae72e154b1513a30"),
            ModelFile("config.json", f"{_MUSICGEN}/config.json", 7866, ""),
            ModelFile("generation_config.json", f"{_MUSICGEN}/generation_config.json", 224, ""),
            ModelFile("model.safetensors", f"{_MUSICGEN}/model.safetensors", 2364427288, "1bdc99d43eb6c775967df24b65b0a9f847c0907e95664698d93b5a1c35f5090d"),
            ModelFile("preprocessor_config.json", f"{_MUSICGEN}/preprocessor_config.json", 275, ""),
            ModelFile("special_tokens_map.json", f"{_MUSICGEN}/special_tokens_map.json", 2201, ""),
            ModelFile("spiece.model", f"{_MUSICGEN}/spiece.model", 791656, "d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86"),
            ModelFile("tokenizer.json", f"{_MUSICGEN}/tokenizer.json", 2422095, ""),
            ModelFile("tokenizer_config.json", f"{_MUSICGEN}/tokenizer_config.json", 2366, ""),
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
