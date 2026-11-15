#!/bin/bash
set -e
exec /workspace/voice-lab/llama-build/bin/llama-server -m /workspace/voice-lab/models/llm/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_0.gguf --host 127.0.0.1 --port 17071 --alias nemotron-lightning --ctx-size 4096 --n-gpu-layers 99 --parallel 1 --jinja
