#!/bin/bash
set -e
cd /workspace/voice-lab/NeMo-Speech.cpp
exec ./build/cuda-server/bin/riva_server --bind 127.0.0.1:17072 --tts.magpie-model /workspace/voice-lab/models/magpie/magpie_tts_multilingual_357m.v2607.f16.gguf --tts.codec-model /workspace/voice-lab/models/codec/nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf --tts.tokenizer-model-dir /workspace/voice-lab/models/magpie/extracted
