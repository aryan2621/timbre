import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, SecretStr

from app.core.huggingface import whoami
from app.core.secrets import hf_token_vault

router = APIRouter()

TOKEN_PATTERN = re.compile(r"^hf_[A-Za-z0-9]{20,}$")


class HuggingFaceTokenIn(BaseModel):
    token: SecretStr


def _status(token: str | None) -> dict[str, Any]:
    if token is None:
        return {"configured": False, "username": None}
    try:
        username = whoami(token)
    except OSError:
        return {"configured": True, "username": None, "reachable": False}
    return {"configured": True, "username": username, "valid": username is not None}


@router.get("/api/credentials/hugging-face")
def get_hugging_face_status() -> dict[str, Any]:
    return _status(hf_token_vault.get())


@router.put("/api/credentials/hugging-face")
def save_hugging_face_token(payload: HuggingFaceTokenIn) -> dict[str, Any]:
    token = payload.token.get_secret_value().strip()
    if not TOKEN_PATTERN.match(token):
        raise HTTPException(status_code=400, detail="That does not look like a Hugging Face token.")
    try:
        username = whoami(token)
    except OSError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Hugging Face.") from exc
    if username is None:
        raise HTTPException(status_code=400, detail="Hugging Face rejected this token.")
    try:
        hf_token_vault.set(token)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"configured": True, "username": username, "valid": True}


@router.delete("/api/credentials/hugging-face")
def delete_hugging_face_token() -> dict[str, Any]:
    hf_token_vault.delete()
    return {"configured": False, "username": None}
