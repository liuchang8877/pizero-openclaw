from __future__ import annotations

import base64
from dataclasses import dataclass
from importlib import import_module
from typing import Callable

import config

_http_session = None


def _get_requests_module():
    return import_module("requests")


def _get_session():
    global _http_session
    if _http_session is None:
        requests = _get_requests_module()
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        _http_session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session


def _request_realtime(payload: dict, timeout: float) -> dict:
    requests = _get_requests_module()
    url = f"{config.REALTIME_STT_BASE_URL.rstrip('/')}{config.REALTIME_STT_HTTP_PATH}"
    headers = {
        "Content-Type": "application/json",
    }
    if config.REALTIME_STT_API_TOKEN:
        headers["Authorization"] = f"Bearer {config.REALTIME_STT_API_TOKEN}"

    try:
        resp = _get_session().post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise RuntimeError(f"Realtime STT request failed: {exc}") from exc

    try:
        body = resp.json()
    except ValueError:
        body = None

    if resp.status_code != 200:
        if isinstance(body, dict):
            message = str(body.get("error", {}).get("message", "")).strip()
            if message:
                raise RuntimeError(message)
        raise RuntimeError(f"Realtime STT failed ({resp.status_code}): {resp.text[:300]}")

    if not isinstance(body, dict):
        raise RuntimeError("Realtime STT returned a non-JSON response.")
    return body


@dataclass
class RealtimeRouteSession:
    session_id: str
    on_partial: Callable[[str], None] | None = None
    latest_partial: str = ""
    latest_final: str = ""
    _closed: bool = False

    def append_audio_chunk(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        payload = _request_realtime(
            {
                "type": "audio.append",
                "session_id": self.session_id,
                "audio_base64": base64.b64encode(chunk).decode("ascii"),
            },
            timeout=max(5.0, config.REALTIME_STT_CONNECT_TIMEOUT_SECONDS),
        )
        self._apply_events(payload.get("events", []))

    def finish(self) -> str:
        if self._closed:
            return self.latest_final
        payload = _request_realtime(
            {
                "type": "session.commit",
                "session_id": self.session_id,
            },
            timeout=max(5.0, config.REALTIME_STT_COMMIT_TIMEOUT_SECONDS),
        )
        self._apply_events(payload.get("events", []))
        final_text = str(payload.get("final_text", "")).strip() or self.latest_final.strip()
        self.latest_final = final_text
        self._closed = True
        return final_text

    def cancel(self) -> None:
        if self._closed:
            return
        try:
            payload = _request_realtime(
                {
                    "type": "session.cancel",
                    "session_id": self.session_id,
                },
                timeout=max(5.0, config.REALTIME_STT_CONNECT_TIMEOUT_SECONDS),
            )
            self._apply_events(payload.get("events", []))
        except Exception as exc:
            print(f"[stt] realtime cancel failed: {exc}")
        finally:
            self._closed = True

    def _apply_events(self, events: list[dict]) -> None:
        for event in events:
            event_type = str(event.get("type", "")).strip()
            text = str(event.get("text", "")).strip()
            if event_type == "transcript.partial":
                self.latest_partial = text
                if self.on_partial and config.REALTIME_STT_SHOW_PARTIAL:
                    self.on_partial(text)
            elif event_type == "transcript.final":
                self.latest_partial = ""
                self.latest_final = text
            elif event_type == "session.completed":
                self.latest_partial = ""
                completed_text = str(event.get("finalText", "")).strip()
                if completed_text:
                    self.latest_final = completed_text


def create_realtime_session(
    on_partial: Callable[[str], None] | None = None,
) -> RealtimeRouteSession:
    payload = _request_realtime(
        {
            "type": "session.start",
            "audio_format": "pcm_s16le",
            "sample_rate": config.AUDIO_SAMPLE_RATE,
            "channels": 1,
            "language": config.REALTIME_STT_LANGUAGE or None,
            "enable_partial": config.REALTIME_STT_SHOW_PARTIAL,
        },
        timeout=max(5.0, config.REALTIME_STT_CONNECT_TIMEOUT_SECONDS),
    )
    session_id = str(payload.get("session_id", "")).strip()
    if not session_id:
        raise RuntimeError("Realtime STT route did not return a session_id.")
    session = RealtimeRouteSession(session_id=session_id, on_partial=on_partial)
    session._apply_events(payload.get("events", []))
    return session

