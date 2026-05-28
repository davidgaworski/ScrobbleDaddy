"""
ScrobbleDaddy - QR Code Setup Server

When Last.fm credentials are not configured, this module:
1. Starts a local web server on port 8080
2. Generates a QR code pointing to the setup page
3. Serves a mobile-friendly form to enter Last.fm credentials
4. Saves credentials to config.json on submit
"""

import json
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

SETUP_PORT = 8080
credentials_updated = threading.Event()


def get_local_ip():
    """Get the Pi's local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScrobbleDaddy Setup</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0c0c14, #1a0a2e);
            color: #f0f0f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .card {
            background: rgba(30, 15, 50, 0.9);
            border: 1px solid rgba(130, 60, 200, 0.3);
            border-radius: 16px;
            padding: 40px 30px;
            width: 100%;
            max-width: 400px;
            backdrop-filter: blur(10px);
        }
        .logo {
            text-align: center;
            margin-bottom: 8px;
            font-size: 36px;
        }
        h1 {
            text-align: center;
            font-size: 24px;
            margin-bottom: 6px;
            background: linear-gradient(135deg, #a855f7, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            text-align: center;
            color: #a0a0b5;
            font-size: 14px;
            margin-bottom: 30px;
        }
        label {
            display: block;
            font-size: 13px;
            color: #a0a0b5;
            margin-bottom: 6px;
            margin-top: 16px;
        }
        input {
            width: 100%;
            padding: 12px 16px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(130, 60, 200, 0.3);
            border-radius: 10px;
            color: #f0f0f5;
            font-size: 16px;
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus {
            border-color: #a855f7;
        }
        input::placeholder { color: #555; }
        button {
            width: 100%;
            padding: 14px;
            margin-top: 28px;
            background: linear-gradient(135deg, #7c3aed, #a855f7);
            border: none;
            border-radius: 10px;
            color: white;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.1s, opacity 0.2s;
        }
        button:active { transform: scale(0.98); opacity: 0.9; }
        .note {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 16px;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🎶</div>
        <h1>ScrobbleDaddy</h1>
        <p class="subtitle">Connect your Last.fm account</p>
        <form method="POST" action="/save">
            <label for="username">Last.fm Username</label>
            <input type="text" id="username" name="username" placeholder="your username" autocapitalize="none" autocorrect="off" required>
            <label for="password">Last.fm Password</label>
            <input type="password" id="password" name="password" placeholder="your password" required>
            <button type="submit">Connect &amp; Start Scrobbling</button>
        </form>
        <p class="note">Your credentials are stored locally on this device only.</p>
    </div>
</body>
</html>"""

SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScrobbleDaddy - Connected!</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0c0c14, #1a0a2e);
            color: #f0f0f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            text-align: center;
        }
        .card {
            background: rgba(30, 15, 50, 0.9);
            border: 1px solid rgba(40, 180, 90, 0.4);
            border-radius: 16px;
            padding: 40px 30px;
            width: 100%;
            max-width: 400px;
        }
        .icon { font-size: 48px; margin-bottom: 16px; }
        h1 { font-size: 22px; margin-bottom: 8px; color: #4ade80; }
        p { color: #a0a0b5; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">✅</div>
        <h1>Connected!</h1>
        <p>ScrobbleDaddy is now scrobbling for <strong>USERNAME</strong>.</p>
        <p style="margin-top:12px;">You can close this page.</p>
    </div>
</body>
</html>"""


class SetupHandler(BaseHTTPRequestHandler):
    config_file = "config.json"

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(SETUP_HTML.encode())

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode()
        params = parse_qs(body)

        username = params.get("username", [""])[0]
        password = params.get("password", [""])[0]

        if username and password:
            # Save to config.json
            with open(self.config_file, "r") as f:
                config = json.load(f)
            config["lastfm"]["username"] = username
            config["lastfm"]["password"] = password
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=4)
                f.write("\n")

            print(f"Last.fm configured for: {username}")

            # Send success page
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            html = SUCCESS_HTML.replace("USERNAME", username)
            self.wfile.write(html.encode())

            # Signal the main app
            credentials_updated.set()
        else:
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()


def generate_qr_surface(url, size=280):
    """Generate a QR code as a pygame surface."""
    import pygame
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="white", back_color=(12, 12, 20))
        img = img.resize((size, size))

        # Convert PIL image to pygame surface
        raw = img.convert("RGB").tobytes()
        surface = pygame.image.fromstring(raw, (size, size), "RGB")
        return surface
    except ImportError:
        # Fallback: just show the URL as text
        return None


def start_setup_server(config_file="config.json"):
    """Start the setup web server and return the URL."""
    SetupHandler.config_file = config_file
    ip = get_local_ip()
    url = f"http://{ip}:{SETUP_PORT}"

    server = HTTPServer(("0.0.0.0", SETUP_PORT), SetupHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"Setup server running at: {url}")
    return url, server
