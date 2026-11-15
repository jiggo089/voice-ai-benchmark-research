import unittest

from nemotron_stream import TurnAudioCapture


class TurnAudioCaptureTests(unittest.TestCase):
    def test_idle_noise_is_bounded_and_speech_is_not_cut(self):
        capture = TurnAudioCapture()
        background = b'\x01\x00' * (16000 * 18)
        capture.add(background)
        self.assertEqual(len(capture.buffer), int(16000 * 2 * 0.8))
        capture.speech_started()
        speech = b'\x22\x11' * (16000 * 3)
        capture.add(speech)
        turn = capture.commit()
        self.assertEqual(len(turn), int(16000 * 2 * 3.8))
        self.assertTrue(turn.endswith(speech))
        self.assertFalse(capture.speaking)
        self.assertEqual(len(capture.buffer), 0)

    def test_interruption_and_next_turn_do_not_inherit_old_audio(self):
        capture = TurnAudioCapture()
        capture.add(b'\x11\x00' * 16000)
        capture.speech_started()
        capture.add(b'\x22\x00' * 16000)
        first = capture.commit()
        capture.add(b'\x33\x00' * 16000)
        capture.speech_started()
        capture.add(b'\x44\x00' * 16000)
        second = capture.commit()
        self.assertNotIn(b'\x11\x00', second)
        self.assertNotIn(b'\x22\x00', second)
        self.assertNotEqual(first, second)

    def test_repeated_speech_start_keeps_current_turn(self):
        capture = TurnAudioCapture()
        capture.speech_started()
        first_half = b'\x01\x00' * 16000
        second_half = b'\x02\x00' * 16000
        capture.add(first_half)
        capture.speech_started()
        capture.add(second_half)
        self.assertEqual(capture.commit(), first_half + second_half)


if __name__ == '__main__':
    unittest.main()
