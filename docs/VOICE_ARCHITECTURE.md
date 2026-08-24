# Voice AI Architecture — AloSM

## System Diagram

```
Browser (React + @livekit/components-react)
  │  [Mic WebRTC audio track]
  ▼
LiveKit Cloud (WebRTC relay, room management)
  │  [AudioFrame stream]
  ▼
Python LiveKit Agent Worker  (src/voice_agent/server.py)
  │  [PCM16 WebSocket chunks]
  ▼
Zipformer ASR Server  (asr_server/server.py — ws://localhost:9000/v1/stt)
  │  [interim/final transcript JSON]
  ▼
LiveKit Agent  (AloSMAgent)
  │  [ChatMessage → LLM API]
  ▼
LLM  (openai/gpt-4.1-mini via LiveKit inference)
  │  [tool calls + text response]
  ▼
FastAPI Business API  (localhost:8000 — geocoding, quote, booking)
  │  [text response]
  ▼
TTS  (openai/gpt-4o-mini-tts, voice=shimmer)
  │  [audio stream]
  ▼
LiveKit Cloud
  │  [WebRTC audio track]
  ▼
Browser (RoomAudioRenderer)
```

## Services

| Service | Port | Technology | Purpose |
|---|---|---|---|
| Frontend | 5173 | React + Vite + @livekit/components-react | UI, mic, speaker |
| Backend API | 8000 | FastAPI | Auth, token, booking, geocoding |
| LiveKit Worker | 8081 (health) | Python livekit-agents | STT→LLM→TTS pipeline |
| ASR Server | 9000 | FastAPI + WebSocket + sherpa-onnx | Zipformer streaming ASR |
| LiveKit Cloud | wss | LiveKit SaaS | WebRTC relay |

## Data Flow Details

### Voice Input Flow

```
1. Browser captures mic via getUserMedia()
2. livekit-client publishes audio track to LiveKit Cloud room
3. LiveKit Agent receives AudioFrame events (16kHz PCM float32)
4. Agent's STT adapter (ZipformerSTT or cloud STT) processes frames
5. If ZipformerSTT:
   a. Connects WebSocket to ASR server (ws://localhost:9000/v1/stt)
   b. Sends handshake: {"type":"start","sample_rate":16000}
   c. Sends binary PCM16 chunks
   d. Receives {"type":"interim","text":"..."} → updates partial
   e. Receives {"type":"final","text":"..."} → commits utterance
   f. LiveKit agent receives STT FINAL_TRANSCRIPT
6. Agent's on_user_turn_completed() fires
7. ASR Confusion normalization + transcript rewrite applied
```

### STT Provider Selection

Set `LIVEKIT_STT_PROVIDER` in `.env`:

| Value | Description | Requires |
|---|---|---|
| `cloud` (default) | OpenAI/Groq cloud STT via LiveKit inference | `LIVEKIT_STT_MODEL=openai/gpt-4o-transcribe` |
| `zipformer` | Local Zipformer ASR via WebSocket | ASR server running + model downloaded |

### LLM + Tool Calling

```
AloSMAgent.on_user_turn_completed()
  └→ LLM receives transcript + conversation history
       └→ LLM may call tools:
            - start_booking() → BookingTask
            - resolve_location() → FastAPI /api/v1/maps/geocode
            - get_quote() → FastAPI /api/v1/quotes
            - create_booking() → FastAPI /api/v1/bookings
```

### Barge-in / Interruption

```
AI is speaking (TTS playing)
  │
User starts speaking (VAD detects voice)
  │
LiveKit interruption: min_words=1, min_duration=0.5s
  │
TTS stream stopped
  │
Agent processes new user turn
```

## Turn Detection Configuration

| Env Var | Default | Description |
|---|---|---|
| `LIVEKIT_TURN_DETECTION` | `vad` | VAD-based (recommended for Vietnamese) |
| `LIVEKIT_ENDPOINTING_MIN_DELAY_SECONDS` | `2.0` | Min silence before utterance ends |
| `LIVEKIT_ENDPOINTING_MAX_DELAY_SECONDS` | `3.0` | Max silence |
| `LIVEKIT_INTERRUPTION_MIN_DURATION_SECONDS` | `0.5` | Min speech to trigger interrupt |
| `LIVEKIT_INTERRUPTION_MIN_WORDS` | `1` | Min words to interrupt |

Vietnamese needs longer pauses than English (2-3s vs 0.5-1s).

## Latency Targets

| Stage | Target | Measurement |
|---|---|---|
| ASR first partial | < 500ms | From start of speech to first interim |
| ASR final | < 700ms after speech end | From endpoint to final transcript |
| LLM TTFT | < 800ms | From final transcript to first token |
| TTS first audio | < 500ms | From LLM output to audio bytes |
| **Speech-to-speech** | **1-2 seconds** | Total end-to-end |

## File Structure

```
P-160/
├── src/
│   ├── frontend/              # React app
│   ├── backend/               # FastAPI business API
│   ├── voice/                 # Voice utilities (ASR, audio, text)
│   │   └── asr/
│   │       └── zipformer/     # Offline Zipformer (batch processing)
│   └── voice_agent/           # LiveKit Agent worker
│       ├── agent.py           # AloSMAgent (LiveKit Agent class)
│       ├── server.py          # Worker entrypoint + session builder
│       ├── config.py          # Settings (LiveKitVoiceSettings)
│       ├── custom_stt.py      # ZipformerSTT adapter
│       ├── tasks.py           # BookingTask (AgentTask)
│       └── ...
├── asr_server/                # Standalone Zipformer streaming server
│   ├── server.py              # FastAPI + WebSocket
│   ├── recognizer.py          # StreamingRecognizer + RecognizerPool
│   └── config.py              # ASRServerSettings
├── scripts/
│   ├── test_asr_stream.py     # Test ASR with WAV file
│   ├── benchmark_asr.py       # Concurrent benchmark
│   └── smoke_test.py          # Integration smoke test
└── docs/
    ├── VOICE_ARCHITECTURE.md  # This file
    ├── TROUBLESHOOTING.md     # Debug guide
    └── MODEL_LICENSE.md       # Model license info
```
