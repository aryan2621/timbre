from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.core.logging_setup import get_logger
from app.core.paths import paths

logger = get_logger("secrets")

SERVICE = "voiceclone-studio"
HF_ACCOUNT = "huggingface-token"


class SecretBackend(Protocol):
    def get(self) -> str | None: ...
    def set(self, value: str) -> None: ...
    def delete(self) -> None: ...


class KeyringBackend:
    def __init__(self, account: str) -> None:
        self._account = account

    def get(self) -> str | None:
        import keyring

        return keyring.get_password(SERVICE, self._account)

    def set(self, value: str) -> None:
        import keyring

        keyring.set_password(SERVICE, self._account, value)

    def delete(self) -> None:
        import keyring
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password(SERVICE, self._account)
        except PasswordDeleteError:
            return


class PrivateFileBackend:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> str | None:
        if not self._path.is_file():
            return None
        return self._path.read_text(encoding="utf-8").strip() or None

    def set(self, value: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
        os.chmod(self._path, 0o600)

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)


class SecretVault:
    def __init__(self, backends: list[SecretBackend]) -> None:
        self._backends = backends

    def get(self) -> str | None:
        for backend in self._backends:
            try:
                value = backend.get()
            except Exception:  # noqa: BLE001 - an unusable backend must not hide the next one
                continue
            if value:
                return value
        return None

    def set(self, value: str) -> None:
        for backend in self._backends:
            try:
                backend.set(value)
                if backend.get() == value:
                    return
            except Exception:  # noqa: BLE001 - fall through to the next backend
                logger.warning("A secret backend could not store the value", exc_info=False)
        raise RuntimeError("No secure storage is available on this system.")

    def delete(self) -> None:
        for backend in self._backends:
            try:
                backend.delete()
            except Exception:  # noqa: BLE001 - best effort across every backend
                continue


hf_token_vault = SecretVault(
    [
        KeyringBackend(HF_ACCOUNT),
        PrivateFileBackend(paths.config_dir / "hf_token"),
    ]
)
