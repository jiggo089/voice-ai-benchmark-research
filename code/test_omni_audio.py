import struct
import unittest
from omni_agent import trim_leading_silence


class OmniAudioTests(unittest.TestCase):
    def test_removes_leading_silence_but_preserves_preroll_and_speech(self):
        silence = bytes(16000 * 2 // 2)
        speech = struct.pack('<h', 500) * 16000
        result = trim_leading_silence(silence + speech)
        self.assertEqual(result, bytes(16000 * 2 * 40 // 1000) + speech)

    def test_silence_and_immediate_speech_are_not_dropped(self):
        silence = bytes(16000)
        speech = struct.pack('<h', 500) * 16000
        self.assertEqual(trim_leading_silence(silence), silence)
        self.assertEqual(trim_leading_silence(speech), speech)

    def test_quiet_speech_is_preserved_including_attack(self):
        leading = bytes(16000 * 2 // 2)
        attack = struct.pack('<h', 80) * 320
        speech = struct.pack('<h', 300) * 3200
        result = trim_leading_silence(leading + attack + speech)
        self.assertTrue(result.endswith(attack + speech))

if __name__ == '__main__':
    unittest.main()
