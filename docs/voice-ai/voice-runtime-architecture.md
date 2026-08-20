# Voice AI runtime architecture

Cập nhật: **2026-08-20** · Trạng thái: `LEGACY_ROLLBACK`.

> File này chỉ mô tả rollback path còn tồn tại trong source. Team-test/current
> target là full LiveKit-native theo
> [`../LIVEKIT_MIGRATION_IMPLEMENTATION.md`](../LIVEKIT_MIGRATION_IMPLEMENTATION.md).

## Transport

| Transport | Use case | Client hiện hành |
|---|---|---|
| `POST /api/v1/voice/turn` | Upload một utterance hoàn chỉnh, nhận transcript + Agent reply + audio | Frontend mic popup |
| `POST /api/v1/voice/speak` | Đọc reply text/typed turn bằng server TTS | Frontend typed reply/playback |
| `WS /api/v1/voice/stream` | PCM16 streaming, VAD, transcript/events và binary TTS | Demo/realtime client |

Voice router chỉ được mount một lần trong `src/backend/main.py` dưới
`/api/v1/voice` khi `VOICE_ENABLED=true`.

## Pipeline chuẩn

```text
Audio hoặc text
  -> input validation / VAD
  -> ASR provider
  -> gazetteer + deterministic normalization
  -> PII masking + transcript rewrite + semantic guard
  -> Backend Session + Core Agent
  -> Backend thực thi typed tool call
  -> deterministic output review
  -> spoken formatter
  -> TTSOrchestrator
  -> audio validator
  -> REST audio/base64 hoặc WS metadata + binary audio
```

Core Agent chỉ quyết định `AgentAction`; Backend sở hữu DB/network/booking/maps/
handoff/TTS side effect. `AgentState` là business conversation truth duy nhất.

## ASR ownership

- `/voice/turn` chọn `auto`, `openai`, `gemini` hoặc `zipformer` bằng
  `VOICE_PROVIDER`.
- WebSocket Gateway dùng ZipFormer khi ready hoặc Groq adapter theo cấu hình.
- Provider thiếu credential/model phải trả typed unavailable error; production
  không sinh transcript giả.
- Transcript cuối phải qua cùng rewrite/semantic guard trước khi tới Agent.

## TTS ownership

Mọi đường TTS phải qua `TTSOrchestrator` để áp dụng:

- booking/safety/PII output review;
- timeout, retry hữu hạn, circuit breaker và fallback voice;
- bounded queue/concurrency và prewarm cache hữu hạn;
- FFmpeg/FFprobe decode, codec/sample-rate/channel/duration/RMS/silence/clipping gate;
- typed failure thay vì audio rỗng hoặc HTTP 500 ngoài kiểm soát.

Frontend không được âm thầm chuyển sang `window.speechSynthesis`.

## ENV không nhập nhằng

- `VOICE_OPENAI_TTS_VOICE`: OpenAI Speech voice của `/voice/turn`.
- `VOICE_TTS_PRIMARY_VOICE`: primary voice của TTS orchestrator.
- `VOICE_TTS_FALLBACK_VOICES`: fallback list.
- `VOICE_TTS_VOICE`: legacy alias chỉ cho Voice runtime.
- `OPENROUTER_API_KEY`: LLM/rewrite gateway, không thay Speech credential.
- `OPENAI_API_KEY`, `GROQ_API_KEY`: provider credential độc lập.

Contract đầy đủ nằm trong `.env.example`.

## State và failure

- Booking chỉ thành công sau explicit confirmation và Backend result xác thực.
- Sửa pickup/destination/vehicle làm vô hiệu quote và confirmation phụ thuộc.
- Low confidence, emergency, complaint, user request, critical tool error hoặc
  unknown side-effect outcome có thể tạo `HANDOFF` có context redacted.
- Telephony transfer/operator queue thật chưa được coi là hoàn thành cho tới khi
  các gate trong `mustdo.md` được đóng.

## Observability và evidence

- Voice health: `/api/v1/voice/health`.
- TTS health/metrics: `/api/v1/voice/tts/health`, `/api/v1/voice/tts/metrics`.
- ZipFormer: `/health/live`, `/health/ready`, `/metrics`,
  `/v1/audio/transcriptions`.
- TTS live evidence: `tts-output-live-report.json`.
- ASR evidence: `zipformer-benchmark.json`.

Không nâng trạng thái production chỉ dựa trên unit test. Release còn phụ thuộc
license, consented corpus, provider SLA, human listening, device matrix và soak test.
