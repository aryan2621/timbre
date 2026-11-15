"""Entry point of the bundled Stable Audio Open Small server (built by desktop/scripts/build-sfx-server.sh).

stable-audio-tools needs Python 3.10 and torch 2.7.1, which cannot share an environment with the API
sidecar, so it runs as its own process. There is no official server, so this is a thin one:

    GET  /health
    POST /generate {prompt, seconds, steps, cfg_scale, seed}  ->  audio/wav (44.1 kHz, stereo)

The model is loaded before the port opens, so "ready" means "can generate".
"""

import argparse
import io
import json
import multiprocessing
import threading
from pathlib import Path

MAX_SECONDS = 11.0


def build_app(model_dir: Path):
    import soundfile as sf
    import torch
    from einops import rearrange
    from fastapi import FastAPI
    from fastapi.responses import Response
    from pydantic import BaseModel, Field
    from stable_audio_tools.inference.generation import generate_diffusion_cond
    from stable_audio_tools.models.factory import create_model_from_config
    from stable_audio_tools.models.utils import load_ckpt_state_dict

    device = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
    config = json.loads((model_dir / "model_config.json").read_text())
    for entry in config["model"]["conditioning"]["configs"]:
        if entry["type"] == "t5":  # use the bundled copy; the default would download t5-base on first use
            entry["config"]["model_path"] = str(model_dir / "t5-base")
    model = create_model_from_config(config)
    model.load_state_dict(load_ckpt_state_dict(str(model_dir / "model.safetensors")))
    model = model.to(device).eval().requires_grad_(False)
    sample_rate, sample_size = config["sample_rate"], config["sample_size"]
    declared = {entry["id"] for entry in config["model"]["conditioning"]["configs"]}
    busy = threading.Lock()  # one render at a time on the GPU

    class Generate(BaseModel):
        prompt: str = Field(min_length=1, max_length=1000)
        seconds: float = Field(10.0, gt=0, le=MAX_SECONDS)
        steps: int = Field(8, ge=1, le=100)
        cfg_scale: float = Field(1.0, ge=0, le=15)
        seed: int = -1

    def conditioning(request: Generate) -> dict:
        # Only what the checkpoint's own config declares; a missing key is an error in stable-audio-tools.
        values = {"prompt": request.prompt, "seconds_start": 0, "seconds_total": request.seconds}
        return {key: value for key, value in values.items() if key in declared}

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok", "device": device}

    @app.post("/generate")
    def generate(request: Generate):
        with busy, torch.no_grad():
            output = generate_diffusion_cond(
                model,
                steps=request.steps,
                cfg_scale=request.cfg_scale,
                conditioning=[conditioning(request)],
                sample_size=sample_size,
                sampler_type="pingpong",
                device=device,
                seed=request.seed,
            )
        audio = rearrange(output, "b d n -> d (b n)").to(torch.float32)[:, : int(request.seconds * sample_rate)]
        peak = audio.abs().max()
        if peak > 0:
            audio = audio / peak
        buffer = io.BytesIO()
        sf.write(buffer, audio.clamp(-1, 1).cpu().numpy().T, sample_rate, format="WAV", subtype="FLOAT")
        return Response(buffer.getvalue(), media_type="audio/wav")

    return app


if __name__ == "__main__":
    # The frozen binary re-launches itself for multiprocessing helpers; without this they parse the
    # server's command line and crash it.
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(build_app(args.model_dir), host=args.host, port=args.port, log_level="info")
