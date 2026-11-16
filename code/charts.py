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

# Early-interruption subset: five runs per configuration, three synthetic voices.
import statistics
groups = {
    'OpenAI Realtime · AEC 3 s': ('openai/realtime-reference','gpt-realtime-2.1-mini (audio)'),
    'OpenAI Realtime · AEC 0 s': ('openai/realtime-reference-aec0','gpt-realtime-2.1-mini (audio)'),
    'GigaAM + Mistral + Qwen3-TTS': ('mistralai/mistral-small-3.1-24b-instruct','nd:qwen3-tts'),
    'GigaAM + Mistral + ESpeech': ('mistralai/mistral-small-3.1-24b-instruct','nd:espeech-tts'),
}
selected = {}
for label,(model,tts) in groups.items():
    cases = [r['cases'][0] for r in runs.values() if r.get('fixture_set')=='complex-v2'
             and r.get('fixture_voice') in ('alloy','nova','onyx')
             and r['config'].get('language')=='ru' and r['config'].get('model')==model
             and r['config'].get('tts')==tts and len(r.get('cases',[]))==1
             and r['cases'][0].get('case')=='interruption']
    if len(cases) != 5: raise ValueError(f'Expected five interruption runs for {label}, got {len(cases)}')
    selected[label] = cases

fig,ax=plt.subplots(figsize=(10,4))
labels=list(selected);values=[statistics.median(c['latency_ms']['interrupt_file_end_to_audio_after_transcript'] for c in selected[x])/1000 for x in labels]
bars=ax.barh(labels[::-1],values[::-1],color=['#72a894','#72a894','#439178','#194e3e']);ax.bar_label(bars,fmt='%.2f s',padding=4);ax.set_xlim(0,8);ax.set_xlabel('Median seconds from end of interruption to first received audio');ax.set_title('Early interruption · Russian · 5 runs per configuration',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/interruption-latency.png',dpi=160)
fig,ax=plt.subplots(figsize=(10,4))
values=[statistics.median(c['interrupt_wer'] for c in selected[x])*100 for x in labels];bars=ax.barh(labels[::-1],values[::-1],color=['#72a894','#72a894','#439178','#c66b47']);ax.bar_label(bars,fmt='%.1f%%',padding=4);ax.set_xlim(0,45);ax.set_xlabel('Median word error rate of interruption transcript · lower is better');ax.set_title('Early interruption: beginning of speech may be lost',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/interruption-wer.png',dpi=160)

ids=['omni-complex-en-20261116','lightning-complex-en']
labels=['Omni · audio input','Lightning · text cascade']
values=[next(c for c in runs[i]['cases'] if c['case']=='interruption')['latency_ms']['interrupt_file_end_to_audio_after_transcript']/1000 for i in ids]
fig,ax=plt.subplots(figsize=(9,3.5));bars=ax.barh(labels[::-1],values[::-1],color=['#6a9ea4','#28624f']);ax.bar_label(bars,fmt='%.2f s',padding=4);ax.set_xlim(0,4);ax.set_xlabel('Seconds from end of interruption to first received audio');ax.set_title('English GB10: interruption · one run each',loc='left',fontweight='bold');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/english-interruption.png',dpi=160)

# All recorded dictation audio latencies; points are individual runs, not comparable model-only timings.
from collections import defaultdict
buckets=defaultdict(list)
for r in runs.values():
 for c in r.get('cases',[]):
  v=c.get('latency_ms',{}).get('file_end_to_first_received_audio')
  if c.get('case')=='dictation' and isinstance(v,(int,float)):
   m=r['config'].get('model','unknown'); buckets[m].append(v/1000)
labels={'openai/realtime-reference':'OpenAI Realtime · RU','openai/realtime-reference-aec0':'OpenAI Realtime, AEC 0 · RU','mistralai/mistral-small-3.1-24b-instruct':'Mistral Small 3.1 · RU','qwen/qwen3.5-9b':'Qwen3.5 9B · RU','vast/nemotron-omni':'Nemotron Omni · EN','vast/nemotron-lightning':'Nemotron Lightning · EN'}
fig,ax=plt.subplots(figsize=(11,4.8))
for i,(model,values) in enumerate(buckets.items()):
 ax.scatter(values,[i]*len(values),s=58,alpha=.75,color='#34836c',edgecolors='white');ax.text(max(values)+.15,i,f'n={len(values)}',va='center',fontsize=9)
ax.set_yticks(range(len(buckets)),[labels.get(k,k) for k in buckets]);ax.set_xlabel('Seconds from end of recording to first received audio');ax.set_title('All recorded dictation timings · different pipelines and scenarios',loc='left',fontweight='bold');ax.set_xlim(0,max(max(v) for v in buckets.values())+1.4);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/all-models-overview.png',dpi=160)

fig,ax=plt.subplots(figsize=(10,4.5))
colors={'alloy':'#337e68','nova':'#de9a37','onyx':'#6776ad'}
for i,(label,cases) in enumerate(selected.items()):
 for voice in ('alloy','nova','onyx'):
  values=[r['cases'][0]['latency_ms']['interrupt_file_end_to_audio_after_transcript']/1000 for r in runs.values() if r.get('fixture_set')=='complex-v2' and r.get('fixture_voice')==voice and r['config'].get('model')==groups[label][0] and r['config'].get('tts')==groups[label][1] and len(r.get('cases',[]))==1 and r['cases'][0].get('case')=='interruption']
  ax.scatter(values,[i]*len(values),label=voice if i==0 else None,color=colors[voice],s=60,alpha=.8,edgecolors='white')
ax.set_yticks(range(len(selected)),list(selected));ax.set_xlabel('Seconds after interrupting recording to received audio');ax.set_title('Input fixture voices: individual interruption runs',loc='left',fontweight='bold');ax.legend(title='Synthetic input voice',loc='lower right');ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True);fig.tight_layout();fig.savefig(ROOT/'charts/input-voice-interruption.png',dpi=160)
