"""
ReWare | https://github.com/ree-verse/ReWare

Remote Desktop Controller - Tkinter GUI.
Launches the WebSocket server and provides a dashboard + live viewer.

Usage:
    python main.py [--port 8765]

Copyright © 2026 Ree-verse. All rights reserved.
Licensed under the MIT License. See LICENSE in the project root for license information.
"""

import argparse
import io
import socket
import threading
import time
import tkinter as tk
from typing import Optional

from PIL import Image, ImageTk

from server import Server

# Theme (Catppuccin Mocha)
class Theme:
    BG = "#1e1e2e"
    SURFACE = "#181825"
    SURFACE_2 = "#313244"
    TEXT = "#cdd6f4"
    SUBTEXT = "#a6adc8"
    OVERLAY = "#585b70"
    GREEN = "#a6e3a1"
    RED = "#f38ba8"
    ACCENT = "#45475a"

class Fonts:
    NORMAL = ("Segoe UI", 10)
    SMALL = ("Segoe UI", 9)
    BOLD = ("Segoe UI", 11, "bold")
    LARGE = ("Segoe UI", 14, "bold")
    XLARGE = ("Segoe UI", 18)

FRAME_POLL_INTERVAL_MS = 16  # ~60 Hz
MOUSE_MOVE_THROTTLE_SEC = 0.033  # ~30 Hz

# Tkinter keysym -> keyboard-library name
_KEY_MAP = {
    # Navigation
    "Return": "enter",
    "KP_Enter": "enter",
    "BackSpace": "backspace",
    "Escape": "escape",
    "Tab": "tab",
    "space": "space",
    "Delete": "delete",
    "Insert": "insert",
    "Home": "home",
    "End": "end",
    "Prior": "page up",
    "Next": "page down",
    "Left": "left",
    "Right": "right",
    "Up": "up",
    "Down": "down",

    # Modifiers
    "Shift_L": "left shift",
    "Shift_R": "right shift",
    "Control_L": "left ctrl",
    "Control_R": "right ctrl",
    "Alt_L": "left alt",
    "Alt_R": "right alt",
    "Win_L": "left windows",
    "Win_R": "right windows",
    "Super_L": "left windows",
    "Super_R": "right windows",
    "Meta_L": "left windows",
    "Meta_R": "right windows",

    # Lock keys
    "Caps_Lock": "caps lock",
    "Num_Lock": "num lock",
    "Scroll_Lock": "scroll lock",

    # Function keys
    **{f"F{i}": f"f{i}" for i in range(1, 25)},

    # System / special
    "Print": "print screen",
    "Sys_Req": "print screen",
    "Pause": "pause",
    "Break": "pause",
    "Menu": "menu",
    "App": "menu",

    # Numpad digits
    "KP_0": "num 0",
    "KP_Insert": "num 0",
    "KP_1": "num 1",
    "KP_End": "num 1",
    "KP_2": "num 2",
    "KP_Down": "num 2",
    "KP_3": "num 3",
    "KP_Next": "num 3",
    "KP_4": "num 4",
    "KP_Left": "num 4",
    "KP_5": "num 5",
    "KP_Begin": "num 5",
    "KP_6": "num 6",
    "KP_Right": "num 6",
    "KP_7": "num 7",
    "KP_Home": "num 7",
    "KP_8": "num 8",
    "KP_Up": "num 8",
    "KP_9": "num 9",
    "KP_Prior": "num 9",

    # Numpad operators
    "KP_Add": "num +",
    "KP_Subtract": "num -",
    "KP_Multiply": "num *",
    "KP_Divide": "num /",
    "KP_Decimal": "num .",
    "KP_Delete": "num .",
    "KP_Separator": "num .",

    # Punctuation / symbols  (US layout keysyms)
    "minus": "-",
    "plus": "+",
    "equal": "=",
    "bracketleft": "[",
    "bracketright": "]",
    "backslash": "\\",
    "slash": "/",
    "semicolon": ";",
    "apostrophe": "'",
    "quoteright": "'",
    "comma": ",",
    "period": ".",
    "grave": "`",
    "asciitilde": "`",
    "exclam": "!",
    "at": "@",
    "numbersign": "#",
    "dollar": "$",
    "percent": "%",
    "asciicircum": "^",
    "ampersand": "&",
    "asterisk": "*",
    "parenleft": "(",
    "parenright": ")",
    "underscore": "_",
    "braceleft": "{",
    "braceright": "}",
    "bar": "|",
    "colon": ":",
    "quotedbl": '"',
    "less": "<",
    "greater": ">",
    "question": "?",

    # Media keys (when WM forwards them)
    "XF86AudioPlay": "play/pause media",
    "XF86AudioPause": "play/pause media",
    "XF86AudioStop": "stop media",
    "XF86AudioNext": "next track",
    "XF86AudioPrev": "previous track",
    "XF86AudioRaiseVolume": "volume up",
    "XF86AudioLowerVolume": "volume down",
    "XF86AudioMute": "volume mute",
}
_MOUSE_BTN = {1: "left", 2: "middle", 3: "right"}


def _get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


class App:
    """Dashboard + remote viewer."""

    def __init__(self, port: int = 8765) -> None:
        self._port = port
        self._setup_window()
        self._setup_server()
        self._setup_state()
        self._build_ui()
        self.server.start()
        self._poll_frame()

    def _setup_window(self) -> None:
        """Initialize the main window."""
        self.root = tk.Tk()
        self.root.title("ReWare - Simple Remote Controller")
        self.root.geometry("1200x800")
        self.root.configure(bg=Theme.BG)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    def _setup_server(self) -> None:
        """Initialize the WebSocket server."""
        self.server = Server(port=self._port)
        self.server.on_frame = self._on_frame
        self.server.on_clients_changed = lambda: self.root.after(0, self._refresh_clients)
        self.server.on_stream_lost = lambda name: self.root.after(0, self._on_stream_lost, name)

    def _setup_state(self) -> None:
        """Initialize application state."""
        self._frame_lock = threading.Lock()
        self._frame_data: Optional[bytes] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._viewing = False
        self._last_move = 0.0

    def _build_ui(self) -> None:
        """Build the user interface."""
        self._build_sidebar()
        self._build_viewer()

    # UI construction

    def _build_sidebar(self) -> None:
        """Build the sidebar with connected clients."""
        side = tk.Frame(self.root, bg=Theme.SURFACE, width=260)
        side.pack(side=tk.LEFT, fill=tk.Y)
        side.pack_propagate(False)

        tk.Label(
            side,
            text="Connected PCs",
            bg=Theme.SURFACE,
            fg=Theme.TEXT,
            font=Fonts.LARGE,
        ).pack(pady=(20, 10))

        self._client_frame = tk.Frame(side, bg=Theme.SURFACE)
        self._client_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        # Bottom info
        info = tk.Frame(side, bg=Theme.SURFACE)
        info.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        tk.Label(
            info,
            text=f"Server  {_get_local_ip()}:{self._port}",
            bg=Theme.SURFACE,
            fg=Theme.SUBTEXT,
            font=Fonts.SMALL,
            anchor="w",
        ).pack(fill=tk.X)

        self._status = tk.StringVar(value="Waiting for connections…")
        tk.Label(
            info,
            textvariable=self._status,
            bg=Theme.SURFACE,
            fg=Theme.OVERLAY,
            font=Fonts.SMALL,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))

    def _build_viewer(self) -> None:
        """Build the main viewer area."""
        viewer = tk.Frame(self.root, bg=Theme.BG)
        viewer.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(viewer, bg=Theme.BG, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._placeholder = tk.Label(
            self._canvas,
            text="Select a PC to connect",
            bg=Theme.BG,
            fg=Theme.OVERLAY,
            font=Fonts.XLARGE,
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Input bindings
        self._bind_inputs()

    def _bind_inputs(self) -> None:
        """Bind input events to handlers."""
        self._canvas.bind("<Motion>", self._on_mouse_move)
        self._canvas.bind("<ButtonPress>", self._on_mouse_btn)
        self._canvas.bind("<ButtonRelease>", self._on_mouse_btn)
        self._canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self._canvas.bind("<Button-4>", lambda _: self._send_scroll(1))
        self._canvas.bind("<Button-5>", lambda _: self._send_scroll(-1))
        self.root.bind("<KeyPress>", self._on_key)
        self.root.bind("<KeyRelease>", self._on_key)

    # Dashboard

    def _refresh_clients(self) -> None:
        """Refresh the client list display."""
        for widget in self._client_frame.winfo_children():
            widget.destroy()

        clients = self.server.get_clients()
        if not clients:
            tk.Label(
                self._client_frame,
                text="No PCs connected",
                bg=Theme.SURFACE,
                fg=Theme.OVERLAY,
                font=Fonts.NORMAL,
            ).pack(pady=30)
            self._status.set("Waiting for connections…")
            return

        self._status.set(f"{len(clients)} PC(s) connected")

        for client_id, client in clients.items():
            self._build_client_card(client_id, client)

    def _build_client_card(self, client_id: str, client) -> None:
        """Build a card for a connected client."""
        card = tk.Frame(self._client_frame, bg=Theme.SURFACE_2, padx=10, pady=8)
        card.pack(fill=tk.X, pady=3)

        # Header row: status dot + name
        header = tk.Frame(card, bg=Theme.SURFACE_2)
        header.pack(fill=tk.X)

        dot, color = ("●", Theme.GREEN) if client.streaming else ("○", Theme.OVERLAY)
        tk.Label(
            header,
            text=dot,
            bg=Theme.SURFACE_2,
            fg=color,
            font=Fonts.NORMAL
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text=f" {client.name}",
            bg=Theme.SURFACE_2,
            fg=Theme.TEXT,
            font=Fonts.BOLD
        ).pack(side=tk.LEFT)

        # One button per monitor
        for monitor in client.monitors:
            self._create_monitor_button(card, client_id, monitor)

        if client.streaming:
            tk.Button(
                card,
                text="Disconnect",
                bg=Theme.RED,
                fg=Theme.SURFACE,
                activebackground="#eba0ac",
                relief=tk.FLAT,
                font=("Segoe UI", 9, "bold"),
                command=self._disconnect,
            ).pack(fill=tk.X, pady=(5, 0))

    def _create_monitor_button(self, parent: tk.Frame, client_id: str, monitor: dict) -> None:
        """Create a button for connecting to a specific monitor."""
        tk.Button(
            parent,
            text=f"Monitor {monitor['id']}  ({monitor['width']}×{monitor['height']})",
            bg=Theme.ACCENT,
            fg=Theme.TEXT,
            activebackground=Theme.OVERLAY,
            relief=tk.FLAT,
            font=Fonts.SMALL,
            command=lambda: self._connect(client_id, monitor["id"]),
        ).pack(fill=tk.X, pady=(5, 0))

    def _connect(self, client_id: str, monitor: int) -> None:
        """Connect to a client's monitor."""
        self.server.select(client_id, monitor)
        self._viewing = True
        self._placeholder.place_forget()
        self._refresh_clients()

    def _disconnect(self) -> None:
        """Disconnect from the current stream."""
        self.server.disconnect()
        self._viewing = False
        with self._frame_lock:
            self._frame_data = None
        self._photo = None
        self._canvas.delete("frame")
        self._placeholder.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self._refresh_clients()

    # Frame rendering

    def _on_frame(self, data: bytes) -> None:
        """Called from the server thread, store for next poll."""
        with self._frame_lock:
            self._frame_data = data

    def _poll_frame(self) -> None:
        """Poll for new frames and render them."""
        with self._frame_lock:
            frame_data = self._frame_data
            self._frame_data = None

        if frame_data and self._viewing:
            self._render_frame(frame_data)

        self.root.after(FRAME_POLL_INTERVAL_MS, self._poll_frame)

    def _render_frame(self, data: bytes) -> None:
        """Render a frame to the canvas."""
        try:
            img = Image.open(io.BytesIO(data))
            canvas_width = self._canvas.winfo_width()
            canvas_height = self._canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                scale = min(canvas_width / img.width, canvas_height / img.height)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)  # Change to Image.Resampling.BILINEAR or Image.Resampling.NEAREST if your computer is not very fast

            self._photo = ImageTk.PhotoImage(img)
            self._canvas.delete("frame")
            self._canvas.create_image(
                canvas_width // 2,
                canvas_height // 2,
                image=self._photo,
                tag="frame",
            )
        except Exception as e:
            print(f"Failed to render frame: {e}.")

    def _on_stream_lost(self, name: str) -> None:
        """Handle stream disconnection."""
        self._disconnect()
        self._status.set(f"Connection lost: {name}")

    # Input forwarding

    def _get_relative_position(self, event: tk.Event) -> Optional[tuple[float, float]]:
        """Convert canvas pixel position to relative [0-1] position over the image."""
        if not self._photo:
            return None

        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()
        image_width = self._photo.width()
        image_height = self._photo.height()

        rel_x = (event.x - (canvas_width - image_width) / 2) / image_width
        rel_y = (event.y - (canvas_height - image_height) / 2) / image_height

        if 0 <= rel_x <= 1 and 0 <= rel_y <= 1:
            return (rel_x, rel_y)
        return None

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Forward throttled mouse-move events to the remote client."""
        if not self._viewing:
            return

        now = time.monotonic()
        if now - self._last_move < MOUSE_MOVE_THROTTLE_SEC:
            return
        self._last_move = now

        position = self._get_relative_position(event)
        if position:
            self.server.send_input(
                {
                    "kind": "mouse",
                    "event": "move",
                    "x": position[0],
                    "y": position[1],
                }
            )

    def _on_mouse_btn(self, event: tk.Event) -> None:
        """Forward mouse press / release to the remote client."""
        if not self._viewing:
            return

        button_name = _MOUSE_BTN.get(event.num)
        if button_name is None:
            return

        self._canvas.focus_set()
        action = "down" if event.type == tk.EventType.ButtonPress else "up"
        position = self._get_relative_position(event)
        if not position:
            return

        self.server.send_input(
            {
                "kind": "mouse",
                "event": action,
                "button": button_name,
                "x": position[0],
                "y": position[1]
            }
        )

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Forward mouse-wheel events to the remote client."""
        if self._viewing and event.delta:
            if abs(event.delta) >= 120:
                clicks = event.delta // 120
            else:
                clicks = 1 if event.delta > 0 else -1
            self._send_scroll(clicks)

    def _send_scroll(self, dy: int) -> None:
        """Send a scroll event with the given vertical delta."""
        self.server.send_input(
            {
                "kind": "mouse",
                "event": "scroll",
                "dy": dy
            }
        )

    def _on_key(self, event: tk.Event) -> None:
        """Forward key press / release to the remote client."""
        if not self._viewing:
            return

        action = "down" if event.type == tk.EventType.KeyPress else "up"
        key = _KEY_MAP.get(event.keysym, event.keysym.lower())
        self.server.send_input(
            {
                "kind": "key",
                "event": action,
                "key": key,
            }
        )

    # Lifecycle

    def _quit(self) -> None:
        """Cleanly stop streaming and destroy the window."""
        self.server.disconnect()
        self.root.destroy()

    def run(self) -> None:
        """Enter the Tkinter main loop."""
        self.root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="ReWare - Simple Remote Desktop Controller")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="websocket server port (default: 8765)",
    )
    args = parser.parse_args()
    App(port=args.port).run()


if __name__ == "__main__":
    main()
