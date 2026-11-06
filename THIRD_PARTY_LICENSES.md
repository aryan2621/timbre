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

---

### Mandatory Acceptable Use & Ethics Policy
Regardless of the model license:
1. **Consent:** You must obtain explicit permission from the voice owner prior to voice cloning.
2. **Deception Prohibited:** You must not use voice clones for impersonation, phishing, social engineering, election deception, or financial fraud.
3. **Watermarking:** Built-in acoustic signatures (Perth) and metadata tags certifying synthetic generation must not be bypassed or removed.

