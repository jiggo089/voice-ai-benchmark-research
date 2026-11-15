#!/bin/bash
set -e
cd /workspace/voice-lab/NeMo-Speech.cpp
exec ./build/cuda-server/bin/nemo-speech serve --host 127.0.0.1 --port 17070 --device cuda:0 --asr-model /workspace/voice-lab/models/asr/nemotron-speech-streaming-en-0.6b.q8_0.gguf --tts-model /workspace/voice-lab/models/magpie/magpie_tts_multilingual_357m.v2607.f16.gguf --codec-model /workspace/voice-lab/models/codec/nemo_nano_codec_22khz_1.89kbps_21.5fps.decoder.f16.gguf --tokenizer-dir /workspace/voice-lab/models/magpie/extracted --no-ui
