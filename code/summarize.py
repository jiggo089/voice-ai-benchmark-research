"""Print portable summary from anonymised synthetic benchmark results."""
import json
import sys
from pathlib import Path

def summarize(path):
    data = json.loads(Path(path).read_text())
    for run in data['runs']:
        for case in run.get('cases', []):
            latency = case.get('latency_ms', {})
            yield (run['id'], run.get('fixture_set') or 'unspecified', run['config'].get('model', ''),
                   run['config'].get('language', ''), case.get('case', ''),
                   latency.get('file_end_to_first_transcript'), latency.get('file_end_to_first_received_audio'),
                   latency.get('interrupt_file_end_to_audio_after_transcript'), case.get('wer'), case.get('interrupt_wer'))

if __name__ == '__main__':
    import csv
    writer = csv.writer(sys.stdout)
    writer.writerow(['run_id', 'fixture', 'model', 'language', 'scenario', 'transcript_ms', 'audio_ms', 'post_interrupt_audio_ms', 'wer', 'interrupt_wer'])
    writer.writerows(summarize(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'data' / 'runs.json'))
