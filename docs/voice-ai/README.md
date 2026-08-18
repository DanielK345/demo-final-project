# Voice AI documentation

Cập nhật: **2026-08-17**. Đây là chỉ mục cho Voice runtime custom hiện hành.

> Không mở rộng thêm custom Voice Gateway/VAD/tool orchestration từ các tài liệu
> dưới đây. Target thay thế đã được chốt tại
> [`../LIVEKIT_MIGRATION_IMPLEMENTATION.md`](../LIVEKIT_MIGRATION_IMPLEMENTATION.md).
> Runtime cũ vẫn được giữ làm baseline cho tới khi LiveKit flow đạt acceptance gate.

| Tài liệu | Vai trò | Trạng thái |
|---|---|---|
| [`voice-runtime-architecture.md`](voice-runtime-architecture.md) | Transport, ASR/rewrite/Agent/TTS pipeline và ownership | `CURRENT` |
| [`voice_local_dev.md`](voice_local_dev.md) | Cài đặt, chạy local và test | `CURRENT` |
| [`transcript-rewrite.md`](transcript-rewrite.md) | Contract sửa transcript và semantic guard | `CURRENT` |
| [`tts-output.md`](tts-output.md) | TTS orchestrator, output review, audio validation và live gate | `CURRENT` |
| [`zipformer-asr.md`](zipformer-asr.md) | ZipFormer local runtime/deploy/benchmark | `CURRENT` |
| [`zipformer-benchmark.json`](zipformer-benchmark.json) | Benchmark máy đọc được | `EVIDENCE` |
| [`tts-output-live-report.json`](tts-output-live-report.json) | TTS→ASR live report | `EVIDENCE` |

Product scope nằm tại [`../PRD_AloSM_Voice.md`](../PRD_AloSM_Voice.md). Trạng thái
toàn hệ thống nằm tại [`../PROJECT_SOURCE_OF_TRUTH.md`](../PROJECT_SOURCE_OF_TRUTH.md).
Các phần cần credential, consent, license, người nghe hoặc hạ tầng thật chỉ nằm tại
[`../../mustdo.md`](../../mustdo.md).

Kế hoạch tuần, prompt tích hợp và báo cáo tiến trình cũ đã được loại khỏi cây tài
liệu hiện hành; dùng Git history nếu cần tra cứu.
