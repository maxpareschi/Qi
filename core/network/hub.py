from __future__ import annotations

import asyncio
from typing import Final

from fastapi import WebSocket

from core.bases.models import QiCallback, QiMessage, QiSession
from core.logger import get_logger
from core.network.message_bus import QiMessageBus

log = get_logger(__name__)


class QiHub:
    """Public façade - developers import only `hub`."""

    def __init__(self) -> None:
        self._bus = QiMessageBus()
        self._hooks: dict[str, list[QiCallback]] = {}

    def on_event(self, name: str):
        """Decorator: @hub.on_event("register")"""

        def _decorator(callback: QiCallback):
            self._hooks.setdefault(name, []).append(callback)
            return callback

        return _decorator

    async def _fire(self, name: str, *args, run_hooks: bool = False) -> None:
        if not run_hooks or name not in self._hooks:
            return

        for callback in self._hooks[name]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(*args)
                else:
                    await asyncio.to_thread(callback, *args)
            except Exception as e:  # noqa: BLE001
                log.error(f"Hook {name} failed: {e}")

    async def register(
        self, socket: WebSocket, info: QiSession, *, run_hooks: bool = False
    ) -> None:
        await self._bus.register(socket, info)
        await self._fire("register", info, run_hooks=run_hooks)

    async def unregister(self, session_id: str, *, run_hooks: bool = False) -> None:
        await self._bus.unregister(session_id)
        await self._fire("unregister", session_id, run_hooks=run_hooks)

    async def publish(self, message: QiMessage, *, run_hooks: bool = False) -> None:
        await self._bus.publish(message)
        await self._fire("publish", message, run_hooks=run_hooks)

    async def request(self, *args, **kwargs):
        return await self._bus.request(*args, **kwargs)

    def on(self, topic: str, *, session_id: str = "__hub__"):
        return self._bus.on(topic, session_id=session_id)

    # fallback for any advanced Bus helper
    def __getattr__(self, item: str):
        return getattr(self._bus, item)


hub: Final = QiHub()
