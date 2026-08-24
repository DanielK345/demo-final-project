# Vietnamese ZipFormer ASR — vận hành production

## Phạm vi đã triển khai

Pipeline nhận audio thật tại `POST /v1/audio/transcriptions`, kiểm tra kích thước/MIME/phần mở rộng,
chuẩn hóa bằng FFmpeg sang mono PCM float32 16 kHz, đưa vào hàng đợi hữu hạn, rồi chạy mô hình
ZipFormer RNNT INT8 trên CPU bằng sherpa-onnx. Event loop không chạy decode/inference trực tiếp;
worker chuyển tác vụ blocking sang thread. Không có transcript mẫu, confidence giả hoặc benchmark giả.

Mô hình được ghim là `hynt/Zipformer-30M-RNNT-6000h`, revision
`24ed30248e1c96bb690c81c24ab4e056f8cd9fce`. Artifact sherpa-onnx dùng checksum SHA-256
`da8b637947091829d7ee9eda23da2a4ec7caa399233a3f4e34eb719fb2ea6b9b`.

> Cảnh báo pháp lý: model card công bố giấy phép `CC-BY-NC-ND-4.0`. Không đưa model này vào dịch vụ
> thương mại trước khi Legal/owner xác nhận quyền sử dụng hoặc thay bằng model có giấy phép phù hợp.

## Chuẩn bị và chạy local

```powershell
.\.venv\Scripts\python.exe scripts\prepare_zipformer_model.py
.\.venv\Scripts\python.exe scripts\live_zipformer_check.py
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

`ASR_REQUIRED=false` cho phép backend khác tiếp tục khởi động khi model thiếu. Production container đặt
`ASR_REQUIRED=true`, do đó startup fail-fast nếu model hỏng/thiếu hoặc warmup thất bại.

Các biến chính:

| Biến | Mặc định | Ý nghĩa |
|---|---:|---|
| `ASR_NUM_THREADS` | 2 | Thread CPU cho mỗi inference |
| `ASR_MAX_CONCURRENCY` | 2 | Số worker inference cố định |
| `ASR_QUEUE_SIZE` | 8 | Hàng đợi hữu hạn; đầy trả 429 |
| `ASR_INFERENCE_TIMEOUT_SECONDS` | 45 | Timeout request |
| `MAX_AUDIO_SIZE_MB` | 15 | Chặn upload trước decode |
| `MAX_AUDIO_DURATION_SECONDS` | 60 | Chặn sau decode |
| `ASR_MODEL_DIR` | `data/models/asr/...` | Thư mục artifact đã xác minh |

## API và trạng thái

```powershell
curl.exe http://localhost:8000/health/live
curl.exe http://localhost:8000/health/ready
curl.exe -F "file=@data/models/asr/sherpa-onnx-zipformer-vi-30M-int8-2026-02-09/test_wavs/0.wav" http://localhost:8000/v1/audio/transcriptions
curl.exe http://localhost:8000/metrics
```

- `/health/live`: process còn sống.
- `/health/ready`: chỉ trả 200 sau load + warmup thật và worker đã chạy; ngược lại trả 503.
- `/metrics`: counters/gauges Prometheus cho request, lỗi, reject, queue, concurrent, thời gian và audio.
- Response transcription có `text`, confidence suy ra từ token log-probability khi runtime cung cấp,
  thời lượng, queue/preprocess/inference/total latency, RTF, request ID và model ID.
- Lỗi dùng schema `{ "error": { "code", "message", "request_id" } }`; response không lộ stack trace.

Frontend `/api/v1/voice/turn` và WebSocket Voice ưu tiên ZipFormer khi model ready. Transcript sau ASR tiếp
tục đi qua lớp LLM rewrite/guardrail hiện có; OpenRouter không thay thế credential Speech.

## Docker và triển khai

Docker image cài FFmpeg, tải artifact đã ghim trong build và kiểm checksum. Model nằm dưới `/opt/models`
để volume `/app/data` của Compose không che mất artifact.

```powershell
docker build -t alosm-zipformer .
docker run --rm -p 8000:8000 --env-file .env alosm-zipformer
```

Kubernetes/ECS nên dùng `/health/live` cho liveness, `/health/ready` cho readiness, giới hạn CPU/RAM,
shutdown grace lớn hơn inference timeout, và scrape `/metrics`. Autoscale theo queue depth, reject rate,
CPU và latency; không chỉ theo số HTTP request.

## Benchmark thật ngày 2026-08-16

Máy đo: Windows 11, AMD Family 25 Model 80, 8 core/16 logical CPU, RAM 15.28 GiB; sherpa-onnx 1.13.4.
Benchmark dùng WAV tiếng Việt đi kèm artifact đã ghim, lặp/cắt PCM thật thành 1/3/5/10/30/60 giây,
concurrency 1/2/4/8. Báo cáo đầy đủ: [zipformer-benchmark.json](zipformer-benchmark.json).

Tại audio 10 giây: p95 lần lượt 188/278/518/1071 ms ở concurrency 1/2/4/8, error rate 0%.
Trên toàn ma trận, max mean RTF 0.0609 và max p95 11.704 giây. Batch 8 request × 60 giây làm RSS
sau batch đạt khoảng 2472.83 MiB. Vì vậy mặc định giữ 2 worker và queue 8; phải benchmark lại trên
máy production trước khi thay đổi.

CPU được báo theo phần trăm của một logical core nên có thể lớn hơn 100%; RSS là mẫu ngay trước/sau
mỗi batch, không được gọi là peak RSS.

## Gate nghiệm thu

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_voice\test_zipformer_audio.py tests\integration\test_zipformer_asr_live.py -q
.\.venv\Scripts\python.exe scripts\benchmark_zipformer.py
.\.venv\Scripts\python.exe -m ruff check src\voice\asr\zipformer src\backend\api\routes\asr.py scripts\benchmark_zipformer.py
```

Integration test chỉ skip khi artifact thật chưa được cài; khi có model, test gọi FastAPI và inference
thật. Không đổi lỗi provider/model thành pass bằng mock.
