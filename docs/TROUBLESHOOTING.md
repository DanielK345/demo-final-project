# Voice AI Troubleshooting Guide

## Agent not dispatched to room

**Symptom**: User joins room but no agent speaks.

**Checks**:
```bash
# 1. Is worker running?
uv run python -m src.voice_agent.server start
# Look for: "registered worker agent_name=alosm-voice"

# 2. Do agent_name values match?
# .env: LIVEKIT_AGENT_NAME=alosm-voice
# tokenSource.ts: LIVEKIT_AGENT_NAME = "alosm-voice"
# server.py: @server.rtc_session(agent_name=...)

# 3. Check LiveKit Cloud dashboard → Workers tab
```

**Fix**: Ensure `LIVEKIT_AGENT_NAME` is identical in `.env` and `tokenSource.ts`.

---

## LIVEKIT_API_SECRET invalid / 401

**Symptom**: Worker fails to register, 401 error in logs.

**Fix**:
```bash
# Verify secret not URL-encoded or truncated
echo $LIVEKIT_API_SECRET | wc -c
# Should be ~43 chars for a typical secret
```

---

## Microphone permission denied

**Symptom**: Browser console shows `NotAllowedError: Permission denied`.

**Fix**: 
- In Chrome: `chrome://settings/content/microphone` → allow localhost
- Must use HTTPS in production (WebRTC requires secure context)

---

## LiveKit disconnected / reconnecting

**Symptom**: Room repeatedly disconnects.

**Checks**:
```bash
# Check network, firewall blocking WebSocket
# LiveKit uses ports 443 (WSS) and 3478/50000-60000 (STUN/TURN/WebRTC)
```

---

## ASR WebSocket timeout

**Symptom**: `ws_timeout session_id=asr-xxx` in ASR server logs.

**Fix**:
- Increase `WS_RECEIVE_TIMEOUT` in `.env`
- Ensure client sends audio frames continuously
- Check network between agent and ASR server

---

## Zipformer model missing

**Symptom**: ASR server logs `Missing ASR model files: ['encoder', ...]`

**Fix**:
```bash
# Download model (see scripts/download_model.py)
uv run python scripts/download_model.py

# Or manually:
mkdir -p data/models/asr
cd data/models/asr
# Download from HuggingFace: hynt/Zipformer-30M-RNNT-Streaming-6000h
```

See `MUST_DO.md` → Mục 11 for full instructions.

---

## sherpa_onnx CUDA unavailable

**Symptom**: `SHERPA_PROVIDER=cuda` fails to load model.

**Fix**:
```env
# In .env, revert to CPU:
SHERPA_PROVIDER=cpu
```

CUDA requires NVIDIA GPU + CUDA runtime + sherpa-onnx built with CUDA.
CPU is sufficient for < 10 concurrent calls.

---

## Wrong sample rate

**Symptom**: ASR produces garbled/empty transcripts.

**Fix**: The agent always sends audio at LiveKit's native rate.
The ASR adapter resamples to 16kHz. If issues persist:
```bash
# Check ASR server logs for sample_rate warnings
# Ensure LIVEKIT agent sends 16kHz audio or resample adapter is active
```

---

## No interim transcript

**Symptom**: `{"type":"interim"}` messages never received.

**Causes**:
1. Model not producing partial results → check `model_type="zipformer2"` in recognizer
2. Audio chunks too small → increase chunk size or check VAD settings
3. Silence in audio → speak clearly into mic

---

## Final transcript never emitted

**Symptom**: Interim appears but no final.

**Causes**:
1. Endpoint detection not triggering → increase silence duration or use `{"type":"finish"}`
2. `rule2_min_trailing_silence` too high → lower to 0.8s for testing

---

## TTS no audio

**Symptom**: LLM responds but no audio plays in browser.

**Checks**:
```bash
# 1. Is RoomAudioRenderer mounted in frontend?
# 2. Is speaker not muted? (speakerMuted state in LiveKitCallContent)
# 3. Check TTS model: must have provider/ prefix
echo $LIVEKIT_TTS_MODEL  # should be "openai/gpt-4o-mini-tts"
```

---

## User cannot interrupt AI

**Symptom**: AI keeps talking even when user speaks.

**Fix**:
```env
LIVEKIT_INTERRUPTION_MIN_DURATION_SECONDS=0.3
LIVEKIT_INTERRUPTION_MIN_WORDS=1
```

Also ensure `allow_interruptions=True` in `generate_reply()` calls.

---

## Running diagnostic

```bash
# Full smoke test
uv run python scripts/smoke_test.py

# Test ASR only
uv run python scripts/test_asr_stream.py path/to/test.wav

# Check agent config
uv run python -c "
from src.voice_agent.config import get_livekit_voice_settings
s = get_livekit_voice_settings()
errors = s.configuration_errors()
print('ERRORS:', errors or 'none')
print('STT provider:', s.livekit_stt_provider)
print('STT model:', s.livekit_stt_model)
"
```
