from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Callable, Protocol

import config


class SttClient(Protocol):
    def transcribe_file(self, wav_path: str) -> str:
        """Return a final transcript for the given WAV file."""

    def start_realtime_session(self, on_partial: Callable[[str], None] | None = None):
        """Return a realtime session object when supported, otherwise ``None``."""


@dataclass
class OneShotSttClient:
    def transcribe_file(self, wav_path: str) -> str:
        transcribe = getattr(import_module("transcribe_openai"), "transcribe")
        return transcribe(wav_path)

    def start_realtime_session(self, on_partial: Callable[[str], None] | None = None):
        return None


@dataclass
class RealtimeSttClient:
    fallback_client: SttClient

    def transcribe_file(self, wav_path: str) -> str:
        if config.REALTIME_STT_FALLBACK_TO_ONESHOT:
            print("[stt] realtime mode requested but streaming path is not wired yet; falling back to one-shot transcription")
            return self.fallback_client.transcribe_file(wav_path)
        raise RuntimeError(
            "Realtime STT mode is configured, but the streaming path is not wired yet. "
            "Set REALTIME_STT_FALLBACK_TO_ONESHOT=true or finish the realtime integration."
        )

    def start_realtime_session(self, on_partial: Callable[[str], None] | None = None):
        create_session = getattr(import_module("transcribe_realtime"), "create_realtime_session")
        return create_session(on_partial=on_partial)


def create_stt_client() -> SttClient:
    one_shot = OneShotSttClient()
    if config.STT_MODE == "realtime":
        return RealtimeSttClient(fallback_client=one_shot)
    return one_shot
