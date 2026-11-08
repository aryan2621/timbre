from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlparse

HF_HOST = "huggingface.co"
WHOAMI_URL = f"https://{HF_HOST}/api/whoami-v2"
REQUEST_TIMEOUT_SECONDS = 15


class _KeepTokenOnSameHostOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urlparse(newurl)
        if target.scheme != "https":
            return None
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and target.hostname != urlparse(req.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected


urllib.request.install_opener(urllib.request.build_opener(_KeepTokenOnSameHostOnly))


def is_hugging_face_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == HF_HOST


def bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def whoami(token: str) -> str | None:
    request = urllib.request.Request(WHOAMI_URL, headers=bearer_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return str(json.load(response).get("name") or "")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return None
        raise
