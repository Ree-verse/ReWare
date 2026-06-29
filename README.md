<h1 align="center">
    ReWare
</h1>

<p align="center">
  <b>Simple Remote Desktop Controller</b>
</p>

<p align="center">
  <a href="https://github.com/ree-verse/ReWare"><img src="https://raw.githubusercontent.com/ree-verse/ReWare/main/assets/ReWare.svg" alt="ReWare logo" height=256></a>
</p>

A lightweight remote desktop tool built with Python. Control any PC on your local network from a single dashboard using WebSockets for communication.

## Preview

Here is an example at 10 FPS, with a JPEG quality of 40%:

https://github.com/user-attachments/assets/d8fa3e88-f8b8-493a-bfee-434bb0f76327

## Features

- **Live Screen Streaming**: Real-time JPEG-encoded screen capture with auto-scaling to fit the viewer
- **Full Mouse Control**: Movement, left/middle/right click, and scroll wheel forwarding
- **Full Keyboard Control**: All standard keys, modifiers, function keys (F1–F24), numpad, navigation, media keys, and system keys
- **Multi-Client Support**: Connect and manage multiple remote PCs simultaneously from a single dashboard
- **Multi-Monitor Support**: Detect and select any individual monitor on the remote PC
- **Automatic Reconnection**: Client retries connection up to 5 times on failure
- **WebSocket Communication**: Lightweight bidirectional protocol over a configurable port (default `8765`)
- **Modern Dark UI**: Clean Tkinter interface with Catppuccin Mocha theme
- **CLI Configuration**: `--port`, `--server`, and `--name` flags for easy setup with sensible defaults
- **Reliable Connection Handling**: Detects disconnects and updates the dashboard automatically

## How It Works

The system has three components:

1. **Controller GUI (`main.py`)** - Runs on *your* machine. Opens a Tkinter dashboard that shows connected PCs and displays a live view of their screens. Your keyboard and mouse inputs on the viewer are captured and forwarded.

2. **WebSocket Server (`server.py`)** - Embedded in the GUI. Listens for incoming client connections, relays screen frames to the viewer, and sends input events back to the active client.

3. **Client (`client.py`)** - Runs on each *remote* PC you want to control. Connects to the server, continuously captures the screen as JPEG frames, and replays any incoming keyboard/mouse events locally.

- **Screen capture** uses [mss](https://github.com/BoboTiG/python-mss) to grab frames, which are compressed to JPEG and sent over the WebSocket as binary messages.
- **Input replay** uses the [keyboard](https://github.com/boppreh/keyboard) and [mouse](https://github.com/boppreh/mouse) libraries to physically reproduce key presses, mouse movements, clicks, and scrolls on the remote machine.
- **Mouse coordinates** are sent as ratios (0–1) relative to the viewed image, then converted to absolute pixel positions on the client side, so mismatched resolutions aren't a problem.

## Requirements

- Python 3.10+

Install dependencies on **both** machines:

```bash
pip install colorama keyboard mouse mss pillow websockets 
```

> [!NOTE]
> On Linux, `keyboard` and `mouse` require root privileges on the client machine.

## Usage

### 1. Start the controller (your machine)

```bash
python main.py
```

The GUI opens and the WebSocket server begins listening. Your local IP and port are shown in the sidebar.

| Flag     | Default | Description          |
|----------|---------|----------------------|
| `--port` | `8765`  | WebSocket server port|

### 2. Start the client (remote machine)

```bash
python client.py --server ws://<controller-ip>:8765
```

Replace `<controller-ip>` with the IP displayed in the controller's sidebar.

| Flag       | Default              | Description                  |
|------------|----------------------|------------------------------|
| `--server` | `ws://HOST:8765`     | WebSocket URL of the server  |
| `--name`   | System hostname      | Display name in the dashboard|

### 3. Connect

Once the client appears in the sidebar, click a monitor button to start streaming. Use **Disconnect** to stop.

## Configuration

These constants in `client.py` can be tuned:

| Constant       | Default | Purpose                          |
|----------------|---------|----------------------------------|
| `JPEG_QUALITY` | `40`    | JPEG compression (1–100)         |
| `FPS`          | `10`    | Target capture framerate         |
| `MAX_RETRIES`  | `5`     | Reconnection attempts on failure |
| `RETRY_DELAY`  | `3`     | Seconds between retries          |

## To Do

- [ ] Hear the sound coming from the remote PC
- [ ] See the mouse movements from the remote user
- [ ] Use encrypted communication (TLS)
- [ ] Configure FPS and JPEG quality from the GUI
- [ ] Scroll horizontally (not supported by the Python `mouse` module)
- [ ] Support all keyboard layouts (not just QWERTY)
- [ ] Connect to multiple PCs at the same time

> [!TIP]
While designed as a simple educational Remote Desktop Controller rather than a full RAT, its core architecture could easily be adapted into one by adding features like persistent reconnection loops for LAN broadcast discovery with appropriate delays, and auto-startup mechanisms. (This tool doesn't use a [reverse-connection](https://en.wikipedia.org/wiki/Reverse_connection) model.)

## Support

If you have questions, suggestions, or want to hang out with other developers, join my Discord server: [Ree-verse GitHub Support](https://discord.gg/ZZfqH9Z4uQ).

## Credits

This project was inspired by [Quasar](https://github.com/quasar/Quasar).
Many thanks to Quasar for the inspiration.

## License

Released under the [MIT License](https://github.com/ree-verse/ReWare/blob/main/LICENSE) © 2026 [Ree-verse](https://github.com/ree-verse).

## Star History

<a href="https://star-history.com/#Ree-verse/ReWare&Timeline">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ree-verse/ReWare&type=Timeline&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=ree-verse/ReWare&type=Timeline" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ree-verse/ReWare&type=Timeline" />
  </picture>
</a>

## Disclaimer

This project is intended for **personal use on your own local network** (e.g., managing your own machines). Do not use it to access devices without explicit authorization.
