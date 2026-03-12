"""
ReWare | https://github.com/ree-verse/ReWare

Remote desktop client - runs on the PC to be controlled.
Captures screen, receives keyboard/mouse events.

Usage:
    python client.py --server ws://<controller-ip>:8765

Copyright © 2026 Ree-verse. All rights reserved.
Licensed under the MIT License. See LICENSE in the project root for license information.
"""

import argparse
import asyncio
import io
import json
import os
import socket

from typing import Any

import keyboard
import mouse
from mss.screenshot import ScreenShot
import websockets
from colorama import Fore, Style
from mss import mss
from PIL import Image

if os.name == "nt":
    from colorama import just_fix_windows_console

    just_fix_windows_console()

SERVER_WS = "ws://HOST:8765"  # Replace HOST with your server's local IP (e.g., 192.168.1.42)
MACHINE_NAME = socket.gethostname()
JPEG_QUALITY = 40
FPS = 10
MAX_RETRIES = 5
RETRY_DELAY = 3


def _colorize(text: str, color: str) -> str:
    """Returns the given text with the specified color."""
    return f"{color}{text}{Style.RESET_ALL}"


def _get_monitors() -> list[dict[str, Any]]:
    """Available monitors (skips index 0 which is the virtual 'all')."""
    with mss() as sct:
        return [
            {"id": i, "width": m["width"], "height": m["height"]}
            for i, m in enumerate(sct.monitors)
            if i > 0
        ]


class Client:
    """Connects to the controller, streams screen, handles input."""

    def __init__(self, server_url: str, name: str) -> None:
        self.server_url = server_url
        self.name = name
        self.streaming = False
        self.monitor = 1
        self._width = 1920
        self._height = 1080
        self._left = 0
        self._top = 0
        self._buff = io.BytesIO()
        self._ws = None

    # Registration and connection

    async def run(self) -> None:
        """Connects to server, registers, and starts the controller and stream tasks."""
        retries = 0
        while retries < MAX_RETRIES:
            try:
                async with websockets.connect(self.server_url, max_size=None) as ws:
                    self._ws = ws
                    await self._register()
                    print(_colorize(f"[+] Connected as '{self.name}'", Fore.GREEN))
                    retries = 0
                    await asyncio.gather(
                        self._handle_messages(),
                        self._stream(),
                    )
            except Exception as e:
                retries += 1
                self.streaming = False
                self._ws = None
                print(
                    _colorize(
                        f"[!] Connection failed, attempt {retries}/{MAX_RETRIES}: {e}.",
                        Fore.YELLOW,
                    )
                )
                if retries < MAX_RETRIES:  # Reconnect on failure
                    await asyncio.sleep(RETRY_DELAY)

        print(_colorize("[x] Max retries reached.", Fore.RED))

    async def _register(self) -> None:
        await self._ws.send(
            json.dumps(
                {
                    "type": "registration",
                    "name": self.name,
                    "monitors": _get_monitors(),
                }
            )
        )
        resp = json.loads(await self._ws.recv())
        if resp.get("type") != "registered":
            raise RuntimeError(
                _colorize("[x] Registration rejected by server.", Fore.RED)
            )

    # Data reception and management

    async def _handle_messages(self) -> None:
        async for raw in self._ws:
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "start_stream":
                self.monitor = msg.get("monitor", 1)
                self._refresh_dimensions()
                self.streaming = True

            elif msg_type == "stop_stream":
                self.streaming = False

            elif msg_type == "input":
                self._handle_input(msg)

    # Screen streaming

    async def _stream(self) -> None:
        """Continuously capture the screen and send frames as JPEG."""
        interval = 1.0 / FPS
        loop = asyncio.get_running_loop()

        with mss() as sct:
            while True:
                if self.streaming:
                    try:
                        monitor = sct.monitors[self.monitor]
                        sct_frame = sct.grab(monitor)
                        jpeg = await loop.run_in_executor(
                            None, self._process_frame, sct_frame
                        )
                        await self._ws.send(jpeg)
                    except (IndexError, KeyError):
                        self.streaming = False
                await asyncio.sleep(interval)

    def _process_frame(self, sct_frame: ScreenShot) -> bytes:
        """Convert a screen capture to JPEG bytes."""
        # frame = Image.frombytes(
        #     mode="RGB", size=sct_frame.size, data=sct_frame.rgb
        # )
        frame = Image.frombytes(
            "RGB", sct_frame.size, sct_frame.bgra, "raw", "BGRX"
        )
        return self._encode_frame_to_jpeg(frame)

    def _refresh_dimensions(self) -> None:
        # Get monitor dimensions for converting ratios to pixel coordinates after
        with mss() as sct:
            if self.monitor < len(sct.monitors):
                monitor = sct.monitors[self.monitor]
                self._width, self._height = monitor["width"], monitor["height"]
                self._left, self._top = monitor["left"], monitor["top"]

    def _encode_frame_to_jpeg(self, frame: Image.Image) -> bytes:
        """Encode an image frame to JPEG bytes."""
        self._buff.seek(0)
        self._buff.truncate(0)
        frame.save(self._buff, format="JPEG", quality=JPEG_QUALITY)
        return self._buff.getvalue()

    # Input replay
    def _handle_input(self, msg: dict) -> None:
        """Handle keyboard and mouse events received from the server."""
        kind, event = msg.get("kind"), msg.get("event")

        if kind == "key":
            try:
                (keyboard.press if event == "down" else keyboard.release)(msg["key"])
            except Exception as e:
                print(_colorize(f"[!] Unknown key: '{msg['key']}': {e}.", Fore.YELLOW))

        elif kind == "mouse":
            if event == "move":
                mouse.move(
                    # Convert ratios to absolute pixels
                    round(msg["x"] * self._width) + self._left,
                    round(msg["y"] * self._height) + self._top,
                    absolute=True,
                )

            elif event in ("down", "up"):
                if "x" in msg and "y" in msg:
                    mouse.move(
                        round(msg["x"] * self._width) + self._left,
                        round(msg["y"] * self._height) + self._top,
                        absolute=True,
                    )
                (mouse.press if event == "down" else mouse.release)(msg["button"])

            elif event == "scroll":
                mouse.wheel(msg["dy"])


def main() -> None:
    parser = argparse.ArgumentParser(description="ReWare - Simple Remote Desktop Client")
    parser.add_argument(
        "--server",
        type=str,
        default=SERVER_WS,
        help="websocket URL of the controller server",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=MACHINE_NAME,
        help="display name for this client",
    )
    args = parser.parse_args()
    asyncio.run(Client(args.server, args.name).run())


if __name__ == "__main__":
    main()
