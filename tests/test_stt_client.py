import types
import unittest
from unittest.mock import patch

import stt_client


class CreateSttClientTests(unittest.TestCase):
    def test_create_stt_client_uses_one_shot_by_default(self):
        with patch.object(stt_client.config, "STT_MODE", "oneshot"):
            client = stt_client.create_stt_client()

        self.assertIsInstance(client, stt_client.OneShotSttClient)

    def test_create_stt_client_uses_realtime_wrapper(self):
        with patch.object(stt_client.config, "STT_MODE", "realtime"):
            client = stt_client.create_stt_client()

        self.assertIsInstance(client, stt_client.RealtimeSttClient)


class RealtimeSttClientTests(unittest.TestCase):
    def test_realtime_client_falls_back_to_one_shot_until_streaming_is_wired(self):
        fallback = stt_client.OneShotSttClient()
        client = stt_client.RealtimeSttClient(fallback_client=fallback)

        with patch.object(stt_client.config, "REALTIME_STT_FALLBACK_TO_ONESHOT", True):
            with patch.object(fallback, "transcribe_file", return_value="hello realtime fallback") as fallback_mock:
                transcript = client.transcribe_file("/tmp/sample.wav")

        self.assertEqual(transcript, "hello realtime fallback")
        fallback_mock.assert_called_once_with("/tmp/sample.wav")

    def test_realtime_client_raises_when_fallback_is_disabled(self):
        client = stt_client.RealtimeSttClient(fallback_client=stt_client.OneShotSttClient())

        with patch.object(stt_client.config, "REALTIME_STT_FALLBACK_TO_ONESHOT", False):
            with self.assertRaisesRegex(RuntimeError, "Realtime STT mode is configured"):
                client.transcribe_file("/tmp/sample.wav")

    def test_realtime_client_delegates_session_creation(self):
        client = stt_client.RealtimeSttClient(fallback_client=stt_client.OneShotSttClient())
        module = types.SimpleNamespace(create_realtime_session=lambda on_partial=None: ("session", on_partial))

        with patch.object(stt_client, "import_module", return_value=module) as import_module_mock:
            session = client.start_realtime_session(on_partial="callback")

        self.assertEqual(session, ("session", "callback"))
        import_module_mock.assert_called_once_with("transcribe_realtime")


class OneShotSttClientTests(unittest.TestCase):
    def test_one_shot_client_delegates_to_transcribe_openai(self):
        client = stt_client.OneShotSttClient()
        module = types.SimpleNamespace(transcribe=lambda wav_path: f"unexpected:{wav_path}")

        with patch.object(stt_client, "import_module", return_value=module) as import_module_mock:
            with patch.object(module, "transcribe", return_value="delegated transcript") as transcribe_mock:
                transcript = client.transcribe_file("/tmp/utterance.wav")

        self.assertEqual(transcript, "delegated transcript")
        import_module_mock.assert_called_once_with("transcribe_openai")
        transcribe_mock.assert_called_once_with("/tmp/utterance.wav")


if __name__ == "__main__":
    unittest.main()
