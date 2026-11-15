# Third-Party Licenses & Model Governance

VoiceClone Studio integrates open-source libraries and machine learning model checkpoints.
Review the commercial and distribution rights below before deploying or monetizing synthesized audio.

| Component / Model | License Type | Commercial Use Permitted? | Notes / Requirements |
| :--- | :--- | :---: | :--- |
| **VoiceClone Studio Core** | MIT License | **YES** | Permissive open-source license. |
| **Chatterbox TTS** | MIT License | **YES** | Zero-shot cloning permitted commercially. Includes Perth acoustic watermark. |
| **CosyVoice 2** | Apache License 2.0 | **YES** | Zero-shot multilingual model from Alibaba, permitted for commercial use with attribution. |
| **PySide6 (Qt 6)** | LGPL v3 | **YES** | Permitted in commercial closed-source applications provided dynamic linking is preserved. |
| **PyTorch** | BSD-3-Clause | **YES** | Standard scientific permissive license. |
| **pyloudnorm** | MIT License | **YES** | EBU R128 loudness normalization. |
| **noisereduce** | MIT License | **YES** | Spectral gating noise reduction. |
| **sounddevice / PortAudio** | MIT / PortAudio | **YES** | Audio capture and playback. |
| **soundfile / libsndfile** | BSD-3 / LGPL-2.1+ | **YES** | Multi-format audio encoding. |
| **mlx-audio** (bundled server) | MIT License | **YES** | Runs Kokoro, Qwen3-TTS and ZONOS3-Mini on Apple Silicon. |
| **Kokoro-82M** | Apache-2.0 | **YES** | hexgrad; MLX conversion by mlx-community. |
| **Qwen3-TTS 0.6B / 1.7B Base** | Apache-2.0 | **YES** | Alibaba Qwen; MLX conversion by mlx-community. |
| **ZONOS3-Mini** | Apache-2.0 | **YES** | Zyphra; MLX conversion by mlx-community. |
| **Underdog Woof** (vendored in `app/vendor/underdog_woof`) | Underdog Non-Commercial License 1.0 | **NO** | Credit required: show "Voice by Underdog Woof". Includes a Mimi-derived decoder (CC BY 4.0, Kyutai). Commercial use needs a licence from Conway. |
| **F5-TTS v1 Base** | CC BY-NC 4.0 (weights), MIT (code) | **NO** | SWivid. Voice cloning; weights are non-commercial. Uses the Vocos vocoder (MIT). |
| **Stable Audio Open Small** (bundled `sfx-server`) | Stability AI Community License | **YES** | Free under $1M annual revenue. Gated on Hugging Face; the user accepts the terms and supplies their own token. |
| **t5-base** (text encoder for Stable Audio Open Small) | Apache-2.0 | **YES** | Google. |

---

### Mandatory Acceptable Use & Ethics Policy
Regardless of the model license:
1. **Consent:** You must obtain explicit permission from the voice owner prior to voice cloning.
2. **Deception Prohibited:** You must not use voice clones for impersonation, phishing, social engineering, election deception, or financial fraud.
3. **Watermarking:** Built-in acoustic signatures (Perth) and metadata tags certifying synthetic generation must not be bypassed or removed.

