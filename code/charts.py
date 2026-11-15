"""Create report charts from the published anonymized run dataset."""
import json
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
runs = {r['id']: r for r in json.loads((ROOT / 'data/runs.json').read_text())['runs']}

def audio(run):
    case = next(c for c in runs[run]['cases'] if c['case'] == 'dictation')
    return case['latency_ms']['file_end_to_first_received_audio'] / 1000

ids = ['31382bf94daa41e8a1526bf26e606c6e','78730a2a83e14dabb045ffe6ca8d11a1','eb795c235e9c4f69a84604ad48178384','2cac3534f7d24656a7b9c34fb63ae8a5','5759704d3afe44e6868c54db4e509c03']
labels = ['OpenAI Realtime','GigaAM + Mistral + Qwen3-TTS','GigaAM + Mistral + ESpeech','Podlodka + Mistral + Qwen3-TTS','Podlodka + Mistral + ESpeech']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(10,4)); bars=ax.barh(labels[::-1],[audio(i) for i in ids][::-1],color=['#77aa96']*4+['#1e5745']);ax.bar_label(bars,fmt='%.2f s',padding=4);ax.set_xlim(0,8);ax.set_xlabel('Seconds from end of recorded speech to first received audio');ax.set_title('Russian complex-v2: one dictation run per configuration',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/russian-dictation.png',dpi=160)
fig,ax=plt.subplots(figsize=(9,3.5));ids=['omni-complex-en-20261116','lightning-complex-en'];labels=['Omni: audio input','Lightning: text cascade'];bars=ax.barh(labels[::-1],[audio(i) for i in ids][::-1],color=['#6a9ea4','#28624f']);ax.bar_label(bars,fmt='%.2f s',padding=4);ax.set_xlim(0,5);ax.set_xlabel('Seconds from end of recorded speech to first received audio');ax.set_title('English complex-v2: one sequential run per configuration',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/english-gb10.png',dpi=160)
