import math
import os
import signal
import struct
import subprocess
import wave
from collections.abc import Iterator

import config

WAV_PATH = "/tmp/utterance.wav"


def check_audio_level(wav_path: str) -> float:
    """Return RMS energy of a 16-bit mono WAV. 0 = silence, ~32768 = max."""
    try:
        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            if n_frames == 0:
                return 0.0
            raw = wf.readframes(n_frames)
            n_samples = n_frames * wf.getnchannels()
            if len(raw) < n_samples * 2:
                return 0.0
            samples = struct.unpack(f"<{n_samples}h", raw[: n_samples * 2])
            return math.sqrt(sum(s * s for s in samples) / n_samples)
    except Exception as e:
        print(f"[rec] audio level check failed: {e}")
        return float("inf")


def _dump_audio_info():
    """Print audio device info for debugging."""
    print("--- /proc/asound/cards ---")
    try:
        with open("/proc/asound/cards") as f:
            print(f.read())
    except Exception as e:
        print(f"  (unavailable: {e})")

    print("--- arecord -l ---")
    try:
        result = subprocess.run(
            ["arecord", "-l"], capture_output=True, text=True, timeout=5
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except Exception as e:
        print(f"  (unavailable: {e})")


class Recorder:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._mode: str | None = None
        self._captured_chunks: list[bytes] = []

    @property
    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def mode(self) -> str | None:
        return self._mode

    def start(self) -> None:
        if self.is_recording:
            return

        if os.path.exists(WAV_PATH):
            os.remove(WAV_PATH)

        cmd = [
            "arecord",
            "-D", config.AUDIO_DEVICE,
            "-f", "S16_LE",
            "-r", str(config.AUDIO_SAMPLE_RATE),
            "-c", "1",
            "-t", "wav",
            WAV_PATH,
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self._mode = "file"
            print(f"[rec] started: {' '.join(cmd)}")
        except FileNotFoundError:
            print("[rec] ERROR: arecord not found — install alsa-utils")
            _dump_audio_info()
            raise
        except Exception:
            _dump_audio_info()
            raise

    def start_streaming(self) -> None:
        if self.is_recording:
            return

        if os.path.exists(WAV_PATH):
            os.remove(WAV_PATH)
        self._captured_chunks = []

        cmd = [
            "arecord",
            "-D", config.AUDIO_DEVICE,
            "-f", "S16_LE",
            "-r", str(config.AUDIO_SAMPLE_RATE),
            "-c", "1",
            "-t", "raw",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._mode = "streaming"
            print(f"[rec] started streaming: {' '.join(cmd)}")
        except FileNotFoundError:
            print("[rec] ERROR: arecord not found — install alsa-utils")
            _dump_audio_info()
            raise
        except Exception:
            _dump_audio_info()
            raise

    def iter_pcm_chunks(self, chunk_ms: int) -> Iterator[bytes]:
        proc = self._proc
        if proc is None or self._mode != "streaming" or proc.stdout is None:
            raise RuntimeError("Recorder is not in streaming mode.")

        bytes_per_ms = max(1, (config.AUDIO_SAMPLE_RATE * 2) // 1000)
        chunk_size = max(bytes_per_ms, bytes_per_ms * max(1, chunk_ms))

        while True:
            chunk = proc.stdout.read(chunk_size)
            if not chunk:
                break
            self._captured_chunks.append(chunk)
            yield chunk
            if len(chunk) < chunk_size and proc.poll() is not None:
                break

    def stop(self) -> str:
        """Stop recording. Returns path to the WAV file."""
        proc = self._proc
        if proc is None:
            return WAV_PATH

        # Send SIGINT for clean WAV header finalization
        try:
            proc.send_signal(signal.SIGINT)
        except OSError:
            pass

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

        stderr = ""
        if proc.stderr:
            try:
                stderr = proc.stderr.read().decode(errors="replace")
            except Exception:
                pass

        self._proc = None
        self._mode = None

        if not os.path.exists(WAV_PATH) or os.path.getsize(WAV_PATH) < 100:
            print(f"[rec] WARNING: WAV file missing or too small")
            if stderr:
                print(f"[rec] stderr: {stderr}")
            _dump_audio_info()

        return WAV_PATH

    def stop_streaming(self) -> str:
        proc = self._proc
        if proc is None:
            return WAV_PATH

        try:
            proc.send_signal(signal.SIGINT)
        except OSError:
            pass

        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

        stderr = ""
        if proc.stderr:
            try:
                stderr = proc.stderr.read().decode(errors="replace")
            except Exception:
                pass

        self._proc = None
        self._mode = None
        self._write_stream_capture_wav()

        if not os.path.exists(WAV_PATH) or os.path.getsize(WAV_PATH) < 100:
            print(f"[rec] WARNING: WAV file missing or too small")
            if stderr:
                print(f"[rec] stderr: {stderr}")
            _dump_audio_info()

        return WAV_PATH

    def _write_stream_capture_wav(self) -> None:
        raw = b"".join(self._captured_chunks)
        with wave.open(WAV_PATH, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(config.AUDIO_SAMPLE_RATE)
            wf.writeframes(raw)

    def cancel(self) -> None:
        """Kill recording without caring about output."""
        proc = self._proc
        if proc is None:
            return
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
        self._proc = None
        self._mode = None
