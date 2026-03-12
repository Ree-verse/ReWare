"""
ReWare | https://github.com/ree-verse/ReWare

WebSocket server for remote desktop control.
Runs on the controlling PC, imported by the GUI.

Copyright © 2026 Ree-verse. All rights reserved.
Licensed under the MIT License. See LICENSE in the project root for license information.
"""

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

import websockets

TIMEOUT = 10


@dataclass
class Client:
    """A connected remote PC."""

    id: str
    name: str
    monitors: list[dict[str, Any]]
    websocket: Any
    streaming: bool = False


class Server:
    """Manages WebSocket connections with remote clients."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.clients_lock = threading.Lock()
        self.clients: dict[str, Client] = {}
        self.active_id: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Callbacks, set by the GUI before calling start()
        self.on_frame: Optional[Callable[[bytes], None]] = None
        self.on_clients_changed: Optional[Callable[[], None]] = None
        self.on_stream_lost: Optional[Callable[[str], None]] = None

    # Lifecycle

    def start(self) -> None:
        """Launch the server in a background daemon thread."""
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self) -> None:
        async with websockets.serve(
            self._handle_client, self.host, self.port, max_size=None
        ) as server:
            await server.serve_forever()

    # Client handler

    async def _handle_client(self, ws) -> None:
        client_id = None

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=TIMEOUT)
            msg = json.loads(raw)
            if msg.get("type") != "registration":
                return

            client_id = uuid.uuid4().hex[:8]
            with self.clients_lock:
                self.clients[client_id] = Client(
                    id=client_id,
                    name=msg["name"],
                    monitors=msg.get("monitors", []),
                    websocket=ws,
                )
            await ws.send(json.dumps({"type": "registered"}))
            self._fire(self.on_clients_changed)

            async for message in ws:
                if isinstance(message, bytes) and client_id == self.active_id:
                    self._fire(self.on_frame, message)

        except (
            websockets.ConnectionClosed,
            asyncio.TimeoutError,
            json.JSONDecodeError,
        ):
            pass

        finally:
            if client_id:
                with self.clients_lock:
                    client = self.clients.pop(client_id, None)
                    was_active = self.active_id == client_id
                    if was_active:
                        self.active_id = None

                if client:
                    if was_active:
                        self._fire(self.on_stream_lost, client.name)
                    self._fire(self.on_clients_changed)

    # Public API (called from the GUI thread)

    def get_clients(self) -> dict[str, Client]:
        """Return a thread-safe snapshot of connected clients."""
        with self.clients_lock:
            return dict(self.clients)

    def select(self, client_id: str, monitor: int) -> None:
        """Start streaming from a specific client and monitor."""
        with self.clients_lock:
            if self.active_id and self.active_id in self.clients:
                self._send(self.active_id, {"type": "stop_stream"})
                self.clients[self.active_id].streaming = False

            if client_id not in self.clients:
                return

            self.active_id = client_id
            self.clients[client_id].streaming = True
            self._send(client_id, {"type": "start_stream", "monitor": monitor})

    def disconnect(self) -> None:
        """Stop the active stream."""
        with self.clients_lock:
            if self.active_id and self.active_id in self.clients:
                self._send(self.active_id, {"type": "stop_stream"})
                self.clients[self.active_id].streaming = False
            self.active_id = None

    def send_input(self, data: dict) -> None:
        """Forward an input event to the active client."""
        with self.clients_lock:
            if self.active_id:
                self._send(self.active_id, {"type": "input", **data})

    # Helpers

    def _send(self, client_id: str, data: dict) -> None:
        if client_id in self.clients and self._loop:
            coroutine = self.clients[client_id].websocket.send(json.dumps(data))
            future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
            future.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)

    @staticmethod
    def _fire(cb, *args) -> None:
        if cb:
            cb(*args)
