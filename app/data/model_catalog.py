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

import json
import os
import platform
import sys
from pathlib import Path

from app.data.models import ModelFile, ModelMetadata

_CHATTERBOX = "https://huggingface.co/ResembleAI/chatterbox/resolve/main"
_ACE_STEP = "https://huggingface.co/Serveurperso/ACE-Step-1.5-GGUF/resolve/main"
_STABLE_AUDIO = "https://huggingface.co/stabilityai/stable-audio-open-1.0/resolve/main"
_POCKET = "https://huggingface.co/kyutai/pocket-tts/resolve/db04f0e653473e5c7333c69686ac92b7460b0c1d/languages/english_2026-10"
_POCKET_TOKENIZER = "https://huggingface.co/kyutai/pocket-tts-without-voice-cloning/resolve/00eac05ed3d16bdc3f6b5d598874019c34a89214/languages/english_2026-09"
_MG_MEDIUM = "https://huggingface.co/facebook/musicgen-medium/resolve/main"
_MG_LARGE = "https://huggingface.co/facebook/musicgen-large/resolve/main"
_MG_MELODY = "https://huggingface.co/facebook/musicgen-melody/resolve/main"
_MUSICGEN = "https://huggingface.co/facebook/musicgen-small/resolve/main"
_QWEN = "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main"
_KOKORO = "https://huggingface.co/mlx-community/Kokoro-82M-bf16/resolve/a71e4d38b236d968966a2002c4c895dbd12b1c3c"
_QWEN_TTS_06B = "https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16/resolve/1eccf1cb2519b5a4e8a95b5f0544f3303568164f"
_QWEN_TTS_17B = "https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16/resolve/a6eb4f68e4b056f1215157bb696209bc82a6db48"
_ZONOS3 = "https://huggingface.co/mlx-community/ZONOS3-Mini/resolve/c3b1320037be83fdbe57586bd6678573de1789f4"
_F5 = "https://huggingface.co/SWivid/F5-TTS/resolve/main/F5TTS_v1_Base"
_VOCOS = "https://huggingface.co/charactr/vocos-mel-24khz/resolve/main"
_SAO_SMALL = "https://huggingface.co/stabilityai/stable-audio-open-small/resolve/main"
_T5_BASE = "https://huggingface.co/google-t5/t5-base/resolve/main"
_WOOF = "https://huggingface.co/ConwayResearch/Underdog-Woof/resolve/be702960539777fc3f698e54335276a8391b00f9"
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
        id="kokoro-82m",
        name="Kokoro 82M",
        version="1.0",
        license_name="Apache 2.0",
        commercial_allowed=True,
        license_notice="Small, fast preset-voice speech model (no cloning), English. Runs through the bundled MLX engine, so Apple Silicon only.",
        total_bytes=332_340_703,
        local_dir="kokoro-82m",
        category="voice-cloning",
        min_memory_gb=2.0,
        gpu_recommended=True,
        files=[
            ModelFile("config.json", f"{_KOKORO}/config.json", 2_351, ""),
            ModelFile("kokoro-v1_0.safetensors", f"{_KOKORO}/kokoro-v1_0.safetensors", 327_115_152, "4e9ecdf03b8b6cf906070390237feda473dc13327cb8d56a43deaa374c02acd8"),
            ModelFile("voices/af_heart.safetensors", f"{_KOKORO}/voices/af_heart.safetensors", 522_320, "2c1c733b0e6576c810e268d3e440c21dea4e0f0131a3ba4cfc98d7fe6136d094"),
            ModelFile("voices/af_bella.safetensors", f"{_KOKORO}/voices/af_bella.safetensors", 522_320, "112d310468cbb3cf23404d3d0b50ad3adf017b87bf38bf9edd15f4ad572df6a3"),
            ModelFile("voices/af_nicole.safetensors", f"{_KOKORO}/voices/af_nicole.safetensors", 522_320, "574656386022c81a029e9a72558191925f44c3de2dad2fa2e45751938557d062"),
            ModelFile("voices/af_sarah.safetensors", f"{_KOKORO}/voices/af_sarah.safetensors", 522_320, "4940072182542f54c1035d1daf4c1cf3136ca9baa9ac57c8e006b4befcc50be6"),
            ModelFile("voices/af_sky.safetensors", f"{_KOKORO}/voices/af_sky.safetensors", 522_320, "957af332330db8e9bd7f9dc449475a946cb0d7d689afef64b91007bbbf20eaa0"),
            ModelFile("voices/am_adam.safetensors", f"{_KOKORO}/voices/am_adam.safetensors", 522_320, "a4f60a3b9c20353c2604a17485ba53260502a758681a84d41e8af53cc559d929"),
            ModelFile("voices/am_michael.safetensors", f"{_KOKORO}/voices/am_michael.safetensors", 522_320, "3940147ded35deba0bb52e8132f89b719298e0520258c34584358aa5a24da2ea"),
            ModelFile("voices/bf_emma.safetensors", f"{_KOKORO}/voices/bf_emma.safetensors", 522_320, "8878a75a6661305849eeb1d6293a7177250193616e161b4c3100636434dfe69f"),
            ModelFile("voices/bf_isabella.safetensors", f"{_KOKORO}/voices/bf_isabella.safetensors", 522_320, "f7b6076f025649699fcfed1a6debf13049a87afdc7aafc8c72b7d81246db6ead"),
            ModelFile("voices/bm_george.safetensors", f"{_KOKORO}/voices/bm_george.safetensors", 522_320, "a3d9b8995cbbe5536f954b6be2a0f1f312f077118ba0d4d2178fc41dc8306672"),
        ],
    ),
    ModelMetadata(
        id="qwen3-tts-0.6b",
        name="Qwen3-TTS 0.6B",
        version="12Hz Base",
        license_name="Apache 2.0",
        commercial_allowed=True,
        license_notice="Lighter Qwen3-TTS voice cloner. Clones a voice from a short clip plus its transcript (made automatically with a Whisper model). Multilingual. Runs through the bundled MLX engine, so Apple Silicon only.",
        total_bytes=2_516_140_464,
        local_dir="qwen3-tts-0.6b",
        category="voice-cloning",
        min_memory_gb=6.0,
        gpu_recommended=True,
        files=[
            ModelFile("config.json", f"{_QWEN_TTS_06B}/config.json", 5_317, ""),
            ModelFile("generation_config.json", f"{_QWEN_TTS_06B}/generation_config.json", 245, ""),
            ModelFile("merges.txt", f"{_QWEN_TTS_06B}/merges.txt", 1_671_839, ""),
            ModelFile("model.safetensors", f"{_QWEN_TTS_06B}/model.safetensors", 1_829_344_448, "d7c7ed3e3464e3e59de0f955b3755891fa8319ff061c3f0307fe2e1343bc122d"),
            ModelFile("model.safetensors.index.json", f"{_QWEN_TTS_06B}/model.safetensors.index.json", 38_573, ""),
            ModelFile("preprocessor_config.json", f"{_QWEN_TTS_06B}/preprocessor_config.json", 127, ""),
            ModelFile("speech_tokenizer/config.json", f"{_QWEN_TTS_06B}/speech_tokenizer/config.json", 2_336, ""),
            ModelFile("speech_tokenizer/configuration.json", f"{_QWEN_TTS_06B}/speech_tokenizer/configuration.json", 76, ""),
            ModelFile("speech_tokenizer/model.safetensors", f"{_QWEN_TTS_06B}/speech_tokenizer/model.safetensors", 682_293_092, "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258"),
            ModelFile("speech_tokenizer/preprocessor_config.json", f"{_QWEN_TTS_06B}/speech_tokenizer/preprocessor_config.json", 234, ""),
            ModelFile("tokenizer_config.json", f"{_QWEN_TTS_06B}/tokenizer_config.json", 7_344, ""),
            ModelFile("vocab.json", f"{_QWEN_TTS_06B}/vocab.json", 2_776_833, ""),
        ],
    ),
    ModelMetadata(
        id="qwen3-tts-1.7b",
        name="Qwen3-TTS 1.7B",
        version="12Hz Base",
        license_name="Apache 2.0",
        commercial_allowed=True,
        license_notice="Higher-quality Qwen3-TTS voice cloner. Clones a voice from a short clip plus its transcript (made automatically with a Whisper model). Multilingual. Runs through the bundled MLX engine, so Apple Silicon only.",
        total_bytes=4_544_210_194,
        local_dir="qwen3-tts-1.7b",
        category="voice-cloning",
        min_memory_gb=10.0,
        gpu_recommended=True,
        files=[
            ModelFile("config.json", f"{_QWEN_TTS_17B}/config.json", 5_317, ""),
            ModelFile("generation_config.json", f"{_QWEN_TTS_17B}/generation_config.json", 245, ""),
            ModelFile("merges.txt", f"{_QWEN_TTS_17B}/merges.txt", 1_671_839, ""),
            ModelFile("model.safetensors", f"{_QWEN_TTS_17B}/model.safetensors", 3_857_414_009, "81fb76175ff74e69be25fef2cc3e54f016df3034f1514c8e1c89da06a3510cff"),
            ModelFile("model.safetensors.index.json", f"{_QWEN_TTS_17B}/model.safetensors.index.json", 38_742, ""),
            ModelFile("preprocessor_config.json", f"{_QWEN_TTS_17B}/preprocessor_config.json", 127, ""),
            ModelFile("speech_tokenizer/config.json", f"{_QWEN_TTS_17B}/speech_tokenizer/config.json", 2_336, ""),
            ModelFile("speech_tokenizer/configuration.json", f"{_QWEN_TTS_17B}/speech_tokenizer/configuration.json", 76, ""),
            ModelFile("speech_tokenizer/model.safetensors", f"{_QWEN_TTS_17B}/speech_tokenizer/model.safetensors", 682_293_092, "836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258"),
            ModelFile("speech_tokenizer/preprocessor_config.json", f"{_QWEN_TTS_17B}/speech_tokenizer/preprocessor_config.json", 234, ""),
            ModelFile("tokenizer_config.json", f"{_QWEN_TTS_17B}/tokenizer_config.json", 7_344, ""),
            ModelFile("vocab.json", f"{_QWEN_TTS_17B}/vocab.json", 2_776_833, ""),
        ],
    ),
    ModelMetadata(
        id="zonos3-mini",
        name="ZONOS3 Mini",
        version="3",
        license_name="Apache 2.0",
        commercial_allowed=True,
        license_notice="Zyphra's multilingual 100M-active-parameter voice model: 27 built-in voices plus cloning from a short clip, no transcript needed, 44.1 kHz. Runs through the bundled MLX engine, so Apple Silicon only.",
        total_bytes=1_408_903_393,
        local_dir="zonos3-mini",
        category="voice-cloning",
        min_memory_gb=4.0,
        gpu_recommended=True,
        files=[
            ModelFile("codec/config.json", f"{_ZONOS3}/codec/config.json", 33_751, ""),
            ModelFile("codec/model.safetensors", f"{_ZONOS3}/codec/model.safetensors", 452_335_255, "1848f4160413d75f7e01bf2919bf23671f97fc0d2fb397c575a0a1ce18a2e9b6"),
            ModelFile("config.json", f"{_ZONOS3}/config.json", 30_333, ""),
            ModelFile("conversion.json", f"{_ZONOS3}/conversion.json", 790, ""),
            ModelFile("model.safetensors", f"{_ZONOS3}/model.safetensors", 909_979_244, "43c056e279153165c91ba691f030d2034bcbb23a760039e6f121fe409245ec66"),
            ModelFile("speaker_encoder/config.json", f"{_ZONOS3}/speaker_encoder/config.json", 123_071, ""),
            ModelFile("speaker_encoder/frontend.npz", f"{_ZONOS3}/speaker_encoder/frontend.npz", 388_670, "523924d33714caf18dbcb5b5a2c2cf9f46afcdfc2889675a726363bde7715a5b"),
            ModelFile("speaker_encoder/model.safetensors", f"{_ZONOS3}/speaker_encoder/model.safetensors", 45_423_622, "81e16f0ff71e7305bb43437cc83a2eb8508638901ad30d3da0d7be89ac410deb"),
            ModelFile("tokenizer.json", f"{_ZONOS3}/tokenizer.json", 559_287, ""),
            ModelFile("voices.json", f"{_ZONOS3}/voices.json", 1_290, ""),
            ModelFile("voices/Ananya_hi_F_1.embedding.npz", f"{_ZONOS3}/voices/Ananya_hi_F_1.embedding.npz", 1_040, "96f93e89e3da2066ace97bbb0d6634e1b627a01ffb163571ba0846c433828e9f"),
            ModelFile("voices/Arjun_hi_M_1.embedding.npz", f"{_ZONOS3}/voices/Arjun_hi_M_1.embedding.npz", 1_040, "02cfa4797a69865d094e0aa54f286e1f8f8b946d967dd5dd066a9b2558b5fbe8"),
            ModelFile("voices/Chaitanya_te_M_1.embedding.npz", f"{_ZONOS3}/voices/Chaitanya_te_M_1.embedding.npz", 1_040, "4cece7d76ee433577f7d6a7bfbc4d78a8fc97372625251a7c34335a3434ed2b6"),
            ModelFile("voices/Cillian_en-Irish_M_1.embedding.npz", f"{_ZONOS3}/voices/Cillian_en-Irish_M_1.embedding.npz", 1_040, "85b02d5eb3c49cc990b779cfaf08a895746e4f41adf9eae3bc8cd6f8dd825d75"),
            ModelFile("voices/Gaspard_fr_M_1.embedding.npz", f"{_ZONOS3}/voices/Gaspard_fr_M_1.embedding.npz", 1_040, "d9ded858cf7f30693ceba01cf2ef0a9bde77585f7b635d009375adcffb35520f"),
            ModelFile("voices/Ginevra_it_F_1.embedding.npz", f"{_ZONOS3}/voices/Ginevra_it_F_1.embedding.npz", 1_040, "7d483d2d3d4bf7b82c6f97a6e74c6ac33560d371e7d695145d16ea82fbe29f39"),
            ModelFile("voices/Haoran_zh-energetic_M_1.embedding.npz", f"{_ZONOS3}/voices/Haoran_zh-energetic_M_1.embedding.npz", 1_040, "48e015f07f50cdd4aa2894f6e1182344042cded0210ce658d407af1c5e7f4a9a"),
            ModelFile("voices/Imogen_en-British_F_1.embedding.npz", f"{_ZONOS3}/voices/Imogen_en-British_F_1.embedding.npz", 1_040, "2f6b7c25d319d29cb3ad994a0190b9a897bbedb019ad7f3201bfd6ee2b740f6e"),
            ModelFile("voices/Jett_en-energetic_M_1.embedding.npz", f"{_ZONOS3}/voices/Jett_en-energetic_M_1.embedding.npz", 1_040, "cd96714be84028f18a38a1192a2811d1be3e1e23c2cba77e4f57f88afbb54e03"),
            ModelFile("voices/Leonor_pt_F_1.embedding.npz", f"{_ZONOS3}/voices/Leonor_pt_F_1.embedding.npz", 1_040, "15a8c46ee0ba03a589372f6fe190c874068e8b38b443f4c6d222fa17739e473a"),
            ModelFile("voices/Liesel_de_F_1.embedding.npz", f"{_ZONOS3}/voices/Liesel_de_F_1.embedding.npz", 1_040, "4020ae38158657da5dd5b27675a860332f21fb4db734b5575b7f42d8f88800bc"),
            ModelFile("voices/Lorenzo_it_M_1.embedding.npz", f"{_ZONOS3}/voices/Lorenzo_it_M_1.embedding.npz", 1_040, "90428c67659a08277d4d0e6da7af8cb89ba8d237b6cd899f437fef824827c65e"),
            ModelFile("voices/Meilin_zh-energetic_F_1.embedding.npz", f"{_ZONOS3}/voices/Meilin_zh-energetic_F_1.embedding.npz", 1_040, "51730de15670ea851f159870f944c3d5df8e339fdce74ce43c9536ec8c7ac0d6"),
            ModelFile("voices/Minjun_ko_M_1.embedding.npz", f"{_ZONOS3}/voices/Minjun_ko_M_1.embedding.npz", 1_040, "61c31b658bafdec9cc3f4b11b1b918a318e4db9f554bc3a25dfa7f88abaf6bbd"),
            ModelFile("voices/Morgana_en-witch_F_1.embedding.npz", f"{_ZONOS3}/voices/Morgana_en-witch_F_1.embedding.npz", 1_040, "3185e130d990731e51a62007285b8f053d8a4ebc66ca5086c8c5804a3f9f70a1"),
            ModelFile("voices/Rodrigo_es_M_1.embedding.npz", f"{_ZONOS3}/voices/Rodrigo_es_M_1.embedding.npz", 1_040, "823fb3b619aca47104bb1dc040f40fc51b944709818390992ae5f3253b3a6408"),
            ModelFile("voices/Rupert_en-British_M_1.embedding.npz", f"{_ZONOS3}/voices/Rupert_en-British_M_1.embedding.npz", 1_040, "90a00601fee898b7d2c45446849236fd95e92cdcc14694f73b8839e29bd31912"),
            ModelFile("voices/Sakura_en-anime_F_1.embedding.npz", f"{_ZONOS3}/voices/Sakura_en-anime_F_1.embedding.npz", 1_040, "c42840b3a35ebcade9d13e67d645140da1bfe1888df60f2abf7eeeb545314f14"),
            ModelFile("voices/Savannah_en-American_F_1.embedding.npz", f"{_ZONOS3}/voices/Savannah_en-American_F_1.embedding.npz", 1_040, "812e02f1f318c0ad4d14280ee06ee4ef80fb0bde6599138762a85821a2db235f"),
            ModelFile("voices/Seoyeon_ko_F_1.embedding.npz", f"{_ZONOS3}/voices/Seoyeon_ko_F_1.embedding.npz", 1_040, "086febcfacba8351726bdad660aca12aa82a6eeee5877c7ca4f2c901f588c3f2"),
            ModelFile("voices/Sravya_te_F_1.embedding.npz", f"{_ZONOS3}/voices/Sravya_te_F_1.embedding.npz", 1_040, "06a157102429ebedb6e956d89e68bcd36895372fd7c6e7bec00a826293239216"),
            ModelFile("voices/Thaddeus_en-announcervoice_M_1.embedding.npz", f"{_ZONOS3}/voices/Thaddeus_en-announcervoice_M_1.embedding.npz", 1_040, "b2b3bc28ed961c100dc35871ee2d4538934412ff9c39692e90023e5067f5404b"),
            ModelFile("voices/Thiago_pt_M_1.embedding.npz", f"{_ZONOS3}/voices/Thiago_pt_M_1.embedding.npz", 1_040, "abd32f1483c304cfdde7af6ca358d750426cf4fc86e96c1af3b10c0bd20ed784"),
            ModelFile("voices/Willow_en-asrm_F_1.embedding.npz", f"{_ZONOS3}/voices/Willow_en-asrm_F_1.embedding.npz", 1_040, "6882c57360d3ff6dbc322ed6ea4ddf11369a04dca9592147a5b6a70f09620c38"),
            ModelFile("voices/Wolfgang_de_M_1.embedding.npz", f"{_ZONOS3}/voices/Wolfgang_de_M_1.embedding.npz", 1_040, "b5c7d23aca415d4d6c8d689b75bc6a728ed5bac167d36a4b1a9a87a81ecf5fca"),
            ModelFile("voices/Wyatt_en-American_M_1.embedding.npz", f"{_ZONOS3}/voices/Wyatt_en-American_M_1.embedding.npz", 1_040, "67352643017465052ca15d30e6b808b68472f7697ab2dabf274b3875f9477984"),
            ModelFile("voices/Ximena_es_F_1.embedding.npz", f"{_ZONOS3}/voices/Ximena_es_F_1.embedding.npz", 1_040, "26d14dc343a682dbb1757a918c40f632128f53b1484506f16c3d45b58e8cdfa0"),
        ],
    ),
    ModelMetadata(
        id="underdog-woof",
        name="Underdog Woof",
        version="2026",
        license_name="Underdog Non-Commercial License 1.0 (credit required)",
        commercial_allowed=False,
        license_notice="Tiny English voice (40 MB, two fixed voices: Juno and Mira) that reads numbers, dates and codes naturally and runs on the CPU. Show \"Voice by Underdog Woof\" in anything you publish with it.",
        total_bytes=40_595_426,
        local_dir="underdog-woof",
        category="voice-cloning",
        min_memory_gb=1.0,
        files=[
            ModelFile("woof_int8.npz", f"{_WOOF}/woof_int8.npz", 40_595_426, "d895fbbe84b8f4f461e3e94ab48b1164353b1988ce8d365f5aa8263d0de1203e"),
        ],
    ),
    ModelMetadata(
        id="f5-tts-v1",
        name="F5-TTS",
        version="v1 Base",
        license_name="CC BY-NC 4.0 (non-commercial)",
        commercial_allowed=False,
        license_notice="Flow-matching voice cloner, English and Chinese, very natural prosody. Clones from a 5-12 second clip and its transcript. The weights are non-commercial.",
        total_bytes=1_402_816_013,
        local_dir="f5-tts",
        category="voice-cloning",
        min_memory_gb=6.0,
        gpu_recommended=True,
        files=[
            ModelFile("model_1250000.safetensors", f"{_F5}/model_1250000.safetensors", 1_348_435_761, "670900fd14e6c458b95da6e9ed317cdb20dbaf7a1c02ac06a05475a9d32b6a38"),
            ModelFile("vocab.txt", f"{_F5}/vocab.txt", 13_800, ""),
            ModelFile("vocos/config.yaml", f"{_VOCOS}/config.yaml", 461, ""),
            ModelFile("vocos/pytorch_model.bin", f"{_VOCOS}/pytorch_model.bin", 54_365_991, "97ec976ad1fd67a33ab2682d29c0ac7df85234fae875aefcc5fb215681a91b2a"),
        ],
    ),
    ModelMetadata(
        id="stable-audio-open-small",
        name="Stable Audio Open Small",
        version="1.0",
        license_name="Stability AI Community License (free under $1M revenue)",
        commercial_allowed=True,
        license_notice="Fast sound effects and short loops, up to 11 seconds, stereo 44.1 kHz. Eight steps instead of fifty, so it renders in a couple of seconds. Gated on Hugging Face: accept the licence on the model page and add your own access token.",
        total_bytes=2_570_663_588,
        local_dir="stable-audio-open-small",
        gated_url="https://huggingface.co/stabilityai/stable-audio-open-small",
        category="sound",
        min_memory_gb=6.0,
        gpu_recommended=True,
        files=[
            ModelFile("model.safetensors", f"{_SAO_SMALL}/model.safetensors", 1_676_829_212, ""),
            ModelFile("model_config.json", f"{_SAO_SMALL}/model_config.json", 5_622, ""),
            # The text encoder it conditions on (t5-base, Apache-2.0), kept local so nothing downloads at run time.
            ModelFile("t5-base/config.json", f"{_T5_BASE}/config.json", 1_208, ""),
            ModelFile("t5-base/generation_config.json", f"{_T5_BASE}/generation_config.json", 147, ""),
            ModelFile("t5-base/model.safetensors", f"{_T5_BASE}/model.safetensors", 891_646_390, "a90903540cc02cbeb7ff9f823f1a80eb778c7e22426a0e620b01c77a5ec8f5b4"),
            ModelFile("t5-base/spiece.model", f"{_T5_BASE}/spiece.model", 791_656, ""),
            ModelFile("t5-base/tokenizer.json", f"{_T5_BASE}/tokenizer.json", 1_389_353, ""),
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
    ModelMetadata(
        id="musicgen-medium",
        name="MusicGen medium",
        version="1.0",
        license_name="CC BY-NC 4.0",
        commercial_allowed=False,
        license_notice="Better music than small: 1.5B parameters, up to 40 seconds. Non-commercial use only. Needs a lot of memory and renders slowly.",
        total_bytes=8281580203,
        local_dir="musicgen-medium",
        category="music",
        min_memory_gb=12.0,
        gpu_recommended=True,
        files=[
            ModelFile("compression_state_dict.bin", f"{_MG_MEDIUM}/compression_state_dict.bin", 236001935, "37d256b525d4117f8bbf790ab448a8e9f4746cd401900fe1ae72e154b1513a30"),
            ModelFile("config.json", f"{_MG_MEDIUM}/config.json", 7866, ""),
            ModelFile("generation_config.json", f"{_MG_MEDIUM}/generation_config.json", 224, ""),
            ModelFile("preprocessor_config.json", f"{_MG_MEDIUM}/preprocessor_config.json", 275, ""),
            ModelFile("special_tokens_map.json", f"{_MG_MEDIUM}/special_tokens_map.json", 2201, ""),
            ModelFile("spiece.model", f"{_MG_MEDIUM}/spiece.model", 791656, "d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86"),
            ModelFile("tokenizer.json", f"{_MG_MEDIUM}/tokenizer.json", 2422095, ""),
            ModelFile("tokenizer_config.json", f"{_MG_MEDIUM}/tokenizer_config.json", 2366, ""),
            ModelFile("pytorch_model.bin", f"{_MG_MEDIUM}/pytorch_model.bin", 8042351585, "b51b0ec25096748bb9a86bf37e41b487024ab2b7077d26cc9e007525f47cd189"),
        ],
    ),
    ModelMetadata(
        id="musicgen-large",
        name="MusicGen large",
        version="1.0",
        license_name="CC BY-NC 4.0",
        commercial_allowed=False,
        license_notice="The best MusicGen quality: 3.3B parameters, up to 40 seconds. Non-commercial. Needs 24 GB or more and renders slowly.",
        total_bytes=13958763040,
        local_dir="musicgen-large",
        category="music",
        min_memory_gb=24.0,
        gpu_recommended=True,
        files=[
            ModelFile("compression_state_dict.bin", f"{_MG_LARGE}/compression_state_dict.bin", 236001935, "37d256b525d4117f8bbf790ab448a8e9f4746cd401900fe1ae72e154b1513a30"),
            ModelFile("config.json", f"{_MG_LARGE}/config.json", 7866, ""),
            ModelFile("generation_config.json", f"{_MG_LARGE}/generation_config.json", 224, ""),
            ModelFile("preprocessor_config.json", f"{_MG_LARGE}/preprocessor_config.json", 275, ""),
            ModelFile("special_tokens_map.json", f"{_MG_LARGE}/special_tokens_map.json", 2201, ""),
            ModelFile("spiece.model", f"{_MG_LARGE}/spiece.model", 791656, "d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86"),
            ModelFile("tokenizer.json", f"{_MG_LARGE}/tokenizer.json", 2422095, ""),
            ModelFile("tokenizer_config.json", f"{_MG_LARGE}/tokenizer_config.json", 2366, ""),
            ModelFile("pytorch_model.bin.index.json", f"{_MG_LARGE}/pytorch_model.bin.index.json", 98104, ""),
            ModelFile("pytorch_model-00001-of-00002.bin", f"{_MG_LARGE}/pytorch_model-00001-of-00002.bin", 9987827539, "a7ed8a0d95eff206263d1ae62955a7b8a7dab11a6b55e953887aea6ed54f85bd"),
            ModelFile("pytorch_model-00002-of-00002.bin", f"{_MG_LARGE}/pytorch_model-00002-of-00002.bin", 3731608779, "f9923d2947297a9883404abfd4041a32cf486c763d36e00eb4f178823bf6bdac"),
        ],
    ),
    ModelMetadata(
        id="musicgen-melody",
        name="MusicGen melody",
        version="1.0",
        license_name="CC BY-NC 4.0",
        commercial_allowed=False,
        license_notice="1.5B parameters tuned for following a melody; here it takes text prompts. Non-commercial use only.",
        total_bytes=6468965679,
        local_dir="musicgen-melody",
        category="music",
        min_memory_gb=12.0,
        gpu_recommended=True,
        files=[
            ModelFile("compression_state_dict.bin", f"{_MG_MELODY}/compression_state_dict.bin", 236001935, "37d256b525d4117f8bbf790ab448a8e9f4746cd401900fe1ae72e154b1513a30"),
            ModelFile("config.json", f"{_MG_MELODY}/config.json", 7781, ""),
            ModelFile("generation_config.json", f"{_MG_MELODY}/generation_config.json", 224, ""),
            ModelFile("preprocessor_config.json", f"{_MG_MELODY}/preprocessor_config.json", 369, ""),
            ModelFile("special_tokens_map.json", f"{_MG_MELODY}/special_tokens_map.json", 2201, ""),
            ModelFile("spiece.model", f"{_MG_MELODY}/spiece.model", 791656, "d60acb128cf7b7f2536e8f38a5b18a05535c9e14c7a355904270e15b0945ea86"),
            ModelFile("tokenizer.json", f"{_MG_MELODY}/tokenizer.json", 2422346, ""),
            ModelFile("tokenizer_config.json", f"{_MG_MELODY}/tokenizer_config.json", 20794, ""),
            ModelFile("model.safetensors.index.json", f"{_MG_MELODY}/model.safetensors.index.json", 68461, ""),
            ModelFile("model-00001-of-00002.safetensors", f"{_MG_MELODY}/model-00001-of-00002.safetensors", 4966269512, "3deb583fd977128b24f59c86d6706f01b35b4ab8553e8355cca6969a9b7440b4"),
            ModelFile("model-00002-of-00002.safetensors", f"{_MG_MELODY}/model-00002-of-00002.safetensors", 1263380400, "01268b3a5f9819026a9ee6b76df35574e7dd521de3e6431c7fad16b44ce5a9c0"),
        ],
    ),
]


def _host_triple() -> str:
    machine = platform.machine().lower()
    arch = "aarch64" if machine in ("arm64", "aarch64") else "x86_64"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    return f"{arch}-pc-windows-msvc" if os.name == "nt" else f"{arch}-unknown-linux-gnu"


def _engine_models() -> list[ModelMetadata]:
    """Bundled-engine servers offered as downloads, from engines.json (written by publish-engines.py)."""
    manifest = json.loads((Path(__file__).with_name("engines.json")).read_text(encoding="utf-8"))
    base = os.environ.get("TIMBRE_ENGINE_BASE_URL", manifest["base_url"]).rstrip("/")
    return [
        ModelMetadata(
            id=engine["id"],
            name=engine["name"],
            version=engine["version"],
            license_name="Bundled engine (see THIRD_PARTY_LICENSES.md)",
            commercial_allowed=True,
            license_notice=engine["notice"],
            total_bytes=engine["size"],
            local_dir=f"engines/{engine['binary']}",
            category="engine",
            min_memory_gb=engine["min_memory_gb"],
            executable=True,
            files=[ModelFile(engine["binary"], f"{base}/{engine['binary']}-{engine['triple']}", engine["size"], engine["sha256"])],
        )
        for engine in manifest["engines"]
        if engine["triple"] == _host_triple()
    ]


CATALOG_MODELS.extend(_engine_models())

_ENGINE_FOR = {
    "kokoro-82m": "engine-mlx-audio",
    "qwen3-tts-0.6b": "engine-mlx-audio",
    "qwen3-tts-1.7b": "engine-mlx-audio",
    "zonos3-mini": "engine-mlx-audio",
    "stable-audio-open-small": "engine-sfx",
}
_ENGINE_IDS = {m.id for m in CATALOG_MODELS if m.category == "engine"}
# Where the engine is not offered (other platforms) these models cannot run, so they are not listed.
CATALOG_MODELS[:] = [m for m in CATALOG_MODELS if m.id not in _ENGINE_FOR or _ENGINE_FOR[m.id] in _ENGINE_IDS]
for _model in CATALOG_MODELS:
    if _model.id in _ENGINE_FOR:
        _model.requires_engine = _ENGINE_FOR[_model.id]


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
