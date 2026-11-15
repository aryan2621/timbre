"""Entry point of the bundled MLX voice server (built by desktop/scripts/build-mlx-server.sh).

Runs mlx-audio's OpenAI-style server. It lives in its own environment, so its pinned
torch/transformers never touch the main API sidecar.
"""

import multiprocessing
import sys


def _disable_espeak() -> None:
    # espeakng-loader's macOS wheel has a build path baked in; the native library aborts the whole
    # process with "phontab: No such file" the first time it runs. mlx-audio already copes with a
    # missing fallback by skipping out-of-dictionary words, so make that the behaviour.
    import misaki.espeak as espeak

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("espeak-ng is not bundled")

    espeak.EspeakFallback = unavailable
    espeak.EspeakG2P = unavailable


if __name__ == "__main__":
    # The frozen binary re-launches itself for multiprocessing helpers (resource tracker); without this
    # they parse the server's command line and crash it.
    multiprocessing.freeze_support()
    _disable_espeak()
    from mlx_audio.server import main

    sys.exit(main())
