"""Uploads the built engine servers to the Hugging Face engines repo and records their size and hash in
app/data/engines.json, which the app reads to offer them on the Models page.

    HF_TOKEN=... python desktop/scripts/publish-engines.py [--no-upload]

Run after build-mlx-server.sh / build-sfx-server.sh. Commit the updated engines.json with the release.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "app" / "data" / "engines.json"
BINARIES = ROOT / "desktop" / "src-tauri" / "binaries"
REPO = "aryan2621/timbre-engines"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    for engine in manifest["engines"]:
        path = BINARIES / f"{engine['binary']}-{engine['triple']}"
        if not path.is_file():
            continue  # another platform's binary, built elsewhere
        engine["size"], engine["sha256"] = path.stat().st_size, sha256(path)
        version = path.with_name(path.name + ".version")
        engine["version"] = re.sub(r"[^\w.+-]", "", version.read_text()) if version.is_file() else engine["version"]
        if not args.no_upload:
            from huggingface_hub import HfApi

            HfApi().upload_file(path_or_fileobj=str(path), path_in_repo=path.name, repo_id=REPO)
        print(f"{engine['binary']}: {engine['size']} bytes {engine['sha256'][:12]}")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
