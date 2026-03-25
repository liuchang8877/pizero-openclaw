import base64
import unittest
from unittest.mock import patch

import transcribe_realtime


class RealtimeRouteSessionTests(unittest.TestCase):
    def test_create_realtime_session_uses_start_route_and_applies_initial_events(self):
        partials = []
        with patch.object(
            transcribe_realtime,
            "_request_realtime",
            return_value={
                "session_id": "sess-1",
                "events": [
                    {"type": "transcript.partial", "text": "你好"},
                ],
            },
        ) as request_mock:
            with patch.object(transcribe_realtime.config, "REALTIME_STT_SHOW_PARTIAL", True):
                session = transcribe_realtime.create_realtime_session(on_partial=partials.append)

        self.assertEqual(session.session_id, "sess-1")
        self.assertEqual(session.latest_partial, "你好")
        self.assertEqual(partials, ["你好"])
        request_mock.assert_called_once()
        self.assertEqual(request_mock.call_args[0][0]["type"], "session.start")

    def test_append_audio_chunk_encodes_base64_and_delivers_partial_events(self):
        session = transcribe_realtime.RealtimeRouteSession(session_id="sess-2")
        with patch.object(
            transcribe_realtime,
            "_request_realtime",
            return_value={
                "events": [
                    {"type": "transcript.partial", "text": "partial text"},
                ],
            },
        ) as request_mock:
            session.append_audio_chunk(b"pcm")

        self.assertEqual(session.latest_partial, "partial text")
        payload = request_mock.call_args[0][0]
        self.assertEqual(payload["type"], "audio.append")
        self.assertEqual(payload["session_id"], "sess-2")
        self.assertEqual(payload["audio_base64"], base64.b64encode(b"pcm").decode("ascii"))

    def test_finish_returns_final_text_and_marks_session_closed(self):
        session = transcribe_realtime.RealtimeRouteSession(session_id="sess-3")
        with patch.object(
            transcribe_realtime,
            "_request_realtime",
            return_value={
                "final_text": "final transcript",
                "events": [
                    {"type": "transcript.final", "text": "final transcript"},
                    {"type": "session.completed", "finalText": "final transcript"},
                ],
            },
        ):
            final_text = session.finish()

        self.assertEqual(final_text, "final transcript")
        self.assertEqual(session.latest_final, "final transcript")
        self.assertTrue(session._closed)

    def test_cancel_marks_session_closed_even_when_route_errors(self):
        session = transcribe_realtime.RealtimeRouteSession(session_id="sess-4")
        with patch.object(
            transcribe_realtime,
            "_request_realtime",
            side_effect=RuntimeError("cancel failed"),
        ):
            session.cancel()

        self.assertTrue(session._closed)


if __name__ == "__main__":
    unittest.main()

