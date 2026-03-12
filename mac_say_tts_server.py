"""Minimal OpenClaw-compatible TTS endpoint backed by macOS `say`."""

import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.environ.get("TTS_HOST", "0.0.0.0")
PORT = int(os.environ.get("TTS_PORT", "18790"))
API_TOKEN = os.environ.get("TTS_API_TOKEN", "")
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "Tingting")


def synthesize_with_say(text: str, voice: str, response_format: str) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
        aiff_path = tmp.name
    suffix = ".wav" if response_format == "wav" else ".aiff"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        out_path = tmp.name
    try:
        cmd = ["say", "-v", voice or DEFAULT_VOICE, "-o", aiff_path, text]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "unknown error").strip()
            raise RuntimeError(f"`say` failed: {err}")
        if response_format == "wav":
            convert = subprocess.run(
                ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, out_path],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if convert.returncode != 0:
                err = (convert.stderr or convert.stdout or "unknown error").strip()
                raise RuntimeError(f"`afconvert` failed: {err}")
        else:
            with open(aiff_path, "rb") as src, open(out_path, "wb") as dst:
                dst.write(src.read())
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass
        try:
            os.remove(aiff_path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "MacSayTTS/0.1"

    def do_POST(self) -> None:
        if self.path != "/v1/audio/speech":
            self.send_error(404, "Not found")
            return

        if API_TOKEN:
            auth = self.headers.get("Authorization", "")
            expected = f"Bearer {API_TOKEN}"
            if auth != expected:
                self.send_error(401, "Unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return

        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(400, "Invalid JSON body")
            return

        text = str(payload.get("input", "")).strip()
        voice = str(payload.get("voice", "")).strip() or DEFAULT_VOICE
        response_format = str(payload.get("response_format", "wav")).strip().lower()

        if not text:
            self.send_error(400, "Missing `input`")
            return
        if response_format not in ("wav", "aiff"):
            self.send_error(400, "Only `wav` or `aiff` response_format is supported")
            return

        try:
            audio_data = synthesize_with_say(text, voice, response_format)
        except Exception as exc:
            self.send_error(500, str(exc))
            return

        self.send_response(200)
        content_type = "audio/wav" if response_format == "wav" else "audio/aiff"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(audio_data)))
        self.end_headers()
        self.wfile.write(audio_data)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[mac-say-tts] {self.address_string()} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[mac-say-tts] listening on http://{HOST}:{PORT}/v1/audio/speech")
    server.serve_forever()


if __name__ == "__main__":
    main()
