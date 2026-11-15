import unittest
from pathlib import Path
from summarize import summarize

class SummaryTest(unittest.TestCase):
    def test_results_have_both_gb10_configurations(self):
        rows = list(summarize(Path(__file__).resolve().parent.parent / 'data' / 'runs.json'))
        cases = {(row[2], row[4]) for row in rows}
        self.assertIn(('vast/nemotron-omni', 'interruption'), cases)
        self.assertIn(('vast/nemotron-lightning', 'interruption'), cases)
        self.assertTrue(all(len(row) == 10 for row in rows))

if __name__ == '__main__':
    unittest.main()
