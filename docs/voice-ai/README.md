# Voice AI documentation

Cập nhật: **2026-08-16**. Đây là chỉ mục duy nhất cho Voice runtime hiện hành.

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
