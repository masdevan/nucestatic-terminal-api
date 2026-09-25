import ipaddress
import socket
import urllib.parse
from fastapi import HTTPException


def clean_webhook_url(raw: str | None) -> str | None:
    url = (raw or "").strip()
    if not url:
        return None
    if len(url) > 255:
        raise HTTPException(status_code=422, detail="webhook must be at most 255 characters")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="webhook must be an http(s) URL")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except Exception:
        raise HTTPException(status_code=422, detail="webhook host could not be resolved")
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise HTTPException(status_code=422, detail="webhook must target a public address")
    return url
