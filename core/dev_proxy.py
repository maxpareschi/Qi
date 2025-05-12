# core/dev_proxy.py
import os
import re

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

DEV = os.getenv("QI_DEV") == "1"
PAT = re.compile(r"^/([^/]+)/")  # '/tray_icon/...'

_PORT_CACHE: dict[str, str] = {}  # addon → http://127.0.0.1:5173
PORT_RANGE = range(5173, 5190)  # scan once if needed


async def _find_port(addon: str) -> str:
    """Return base URL of vite dev-server serving this addon."""
    if addon in _PORT_CACHE:
        return _PORT_CACHE[addon]

    async with httpx.AsyncClient(timeout=0.3) as c:
        for port in PORT_RANGE:
            try:
                r = await c.get(f"http://127.0.0.1:{port}/__qi_ping")
                if r.headers.get("X-Qi-Addon") == addon:
                    url = f"http://127.0.0.1:{port}"
                    _PORT_CACHE[addon] = url
                    return url
            except httpx.RequestError:
                continue
    raise RuntimeError(f"dev-server for {addon} not found")


async def dev_proxy(request: Request, call_next):
    if DEV:
        m = PAT.match(request.url.path)
        if m:
            addon = m.group(1)
            try:
                root = await _find_port(addon)
            except RuntimeError as e:
                return JSONResponse({"error": str(e)}, 502)

            target = f"{root}{request.url.path}"
            if request.url.query:
                target += f"?{request.url.query}"

            async with httpx.AsyncClient(timeout=None) as c:
                if request.scope["type"] == "http":
                    resp = await c.request(
                        request.method,
                        target,
                        headers=request.headers.raw,
                        content=await request.body(),
                    )
                    return Response(
                        resp.content, status_code=resp.status_code, headers=resp.headers
                    )
    return await call_next(request)
