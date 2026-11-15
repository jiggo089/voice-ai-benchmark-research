#!/bin/bash
set -e
export HF_HOME=/workspace/voice-lab/huggingface
export VLLM_NO_USAGE_STATS=1
export MAX_JOBS=4
export CMAKE_BUILD_PARALLEL_LEVEL=4
exec /workspace/voice-lab/omni-venv/bin/vllm serve nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4 --host 127.0.0.1 --port 17073 --served-model-name nemotron-omni --chat-template-content-format string --max-model-len 4096 --trust-remote-code --limit-mm-per-prompt '{"audio": {"count": 1, "length": 320000}, "image": 0, "video": 0}' --kv-cache-dtype fp8 --max-num-seqs 1 --gpu-memory-utilization 0.38 --enforce-eager --moe-backend cutlass --reasoning-parser nemotron_v3 --enable-auto-tool-choice --tool-call-parser qwen3_coder
