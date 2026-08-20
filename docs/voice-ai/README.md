# Legacy Voice AI và evaluation evidence

Cập nhật: **2026-08-20**. Đây là chỉ mục cho legacy rollback path và evidence cũ.

> Không mở rộng thêm custom Voice Gateway/VAD/tool orchestration từ các tài liệu
> dưới đây. Target thay thế đã được chốt tại
> [`../LIVEKIT_MIGRATION_IMPLEMENTATION.md`](../LIVEKIT_MIGRATION_IMPLEMENTATION.md).
> Runtime LiveKit hiện là team-test baseline. Các file dưới đây không được dùng để
> mở rộng custom voice pipeline; chỉ giữ cho rollback, so sánh Phase 4 và evidence.

| Tài liệu | Vai trò | Trạng thái |
|---|---|---|
| [`voice-runtime-architecture.md`](voice-runtime-architecture.md) | Legacy transport/ASR/rewrite/Agent/TTS ownership | `LEGACY_ROLLBACK` |
| [`voice_local_dev.md`](voice_local_dev.md) | Legacy local runbook | `LEGACY_ROLLBACK` |
| [`transcript-rewrite.md`](transcript-rewrite.md) | Legacy transcript rewrite contract | `REFERENCE` |
| [`tts-output.md`](tts-output.md) | Legacy TTS orchestrator contract | `REFERENCE` |
| [`zipformer-asr.md`](zipformer-asr.md) | ZipFormer runtime/deploy/benchmark | `REFERENCE` |
| [`zipformer-benchmark.json`](zipformer-benchmark.json) | Benchmark máy đọc được | `EVIDENCE` |
| [`tts-output-live-report.json`](tts-output-live-report.json) | TTS→ASR live report | `EVIDENCE` |

Product scope nằm tại [`../PRD_AloSM_Voice.md`](../PRD_AloSM_Voice.md). Trạng thái
toàn hệ thống nằm tại [`../PROJECT_SOURCE_OF_TRUTH.md`](../PROJECT_SOURCE_OF_TRUTH.md).
Các phần cần credential, consent, license, người nghe hoặc hạ tầng thật chỉ nằm tại
[`../../mustdo.md`](../../mustdo.md).

Kế hoạch tuần, prompt tích hợp và báo cáo tiến trình cũ đã được loại khỏi cây tài
liệu hiện hành; dùng Git history nếu cần tra cứu.
