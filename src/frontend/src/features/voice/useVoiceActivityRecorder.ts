import { useEffect, useRef, useState } from "react";

// Ngưỡng năng lượng (RMS) tính là "có tiếng nói" — cùng bậc độ lớn với
// VOICE_MIN_UTTERANCE_RMS=0.01 ở backend (.env.example, dùng cho pipeline giọng nói
// khác) nhưng đặt cao hơn 1 chút vì đây là micro thô của trình duyệt (chưa qua xử lý
// tiếng ồn nền như audio nhận ở server).
const SPEECH_RMS_THRESHOLD = 0.02;
// Khoảng lặng liên tục trước khi coi là NGƯỜI DÙNG ĐÃ NÓI XONG câu — khớp
// VOICE_VAD_SILENCE_MS=900 ở backend, giữ cùng "nhịp" chờ giữa các lượt nói.
const SILENCE_HANGOVER_MS = 900;
// Bỏ qua đoạn ghi quá ngắn (tiếng ho, gõ bàn, va chạm micro...) — không đủ để là 1
// câu nói thật, tránh gửi rác lên backend.
const MIN_UTTERANCE_MS = 300;
const POLL_INTERVAL_MS = 60;

export interface UseVoiceActivityRecorderOptions {
  // Có nên đang lắng nghe hay không (đang trong cuộc gọi, chưa tự tắt mic, AI hiện
  // không đang xử lý/trả lời) — điều khiển từ ngoài (VoiceCallPanel) thay vì hook tự
  // quyết định, để không lẫn với vòng đời state của cuộc gọi.
  active: boolean;
  permissionGranted: boolean;
  onUtterance: (audio: Blob) => Promise<void> | void;
  onError?: (error: Error) => void;
}

/**
 * Lắng nghe micro LIÊN TỤC (không cần bấm nút) — tự phát hiện lúc người dùng bắt đầu
 * nói (năng lượng âm thanh vượt ngưỡng) và tự phát hiện lúc nói xong (im lặng đủ lâu),
 * rồi tự gửi đoạn ghi âm đó đi xử lý — đúng cảm giác một cuộc gọi thật, không phải
 * "bấm mic mới được nói, xong lại phải chờ". Xin quyền micro đúng 1 lần khi mount (giữ
 * nguyên stream xuyên suốt cuộc gọi), chỉ tạm dừng/tiếp tục ĐỌC năng lượng theo
 * `active` — không xin lại quyền mỗi lượt nói.
 */
export function useVoiceActivityRecorder({
  active,
  permissionGranted,
  onUtterance,
  onError,
}: UseVoiceActivityRecorderOptions): { isSpeechDetected: boolean } {
  const [isSpeechDetected, setIsSpeechDetected] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  // Tham số kiểu <ArrayBuffer> tường minh — lib.dom.d.ts bản mới đòi
  // getFloatTimeDomainData() nhận đúng Float32Array<ArrayBuffer>, không phải
  // ArrayBufferLike (kiểu suy ra mặc định của Float32Array trần).
  const dataArrayRef = useRef<Float32Array<ArrayBuffer> | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const speechStartRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const pollHandleRef = useRef<number | null>(null);
  const suppressNextRef = useRef(false);

  const onUtteranceRef = useRef(onUtterance);
  onUtteranceRef.current = onUtterance;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  // Xin quyền micro + dựng AnalyserNode đúng 1 lần cho cả cuộc gọi — giải phóng khi
  // component unmount (đóng popup = kết thúc cuộc gọi = nhả micro thật).
  useEffect(() => {
    if (!permissionGranted) return;
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const AudioContextCtor =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const audioContext = new AudioContextCtor();
        void audioContext.resume().catch(() => undefined);
        const source = audioContext.createMediaStreamSource(stream);
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);
        audioContextRef.current = audioContext;
        analyserRef.current = analyser;
        // Cấp phát tường minh qua ArrayBuffer (không phải ArrayBufferLike suy ra từ
        // constructor số) — lib.dom.d.ts bản mới đòi getFloatTimeDomainData() nhận
        // đúng Float32Array<ArrayBuffer>.
        dataArrayRef.current = new Float32Array(new ArrayBuffer(analyser.fftSize * Float32Array.BYTES_PER_ELEMENT));
      })
      .catch(() => {
        onErrorRef.current?.(new Error("Không thể truy cập micro. Vui lòng cấp quyền micro cho trình duyệt."));
      });

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      void audioContextRef.current?.close().catch(() => undefined);
      audioContextRef.current = null;
    };
  }, [permissionGranted]);

  useEffect(() => {
    const stopPolling = () => {
      if (pollHandleRef.current !== null) {
        window.clearInterval(pollHandleRef.current);
        pollHandleRef.current = null;
      }
    };

    if (!active) {
      stopPolling();
      // Nếu đang ghi dở khi bị tạm dừng (vd người dùng tự bấm tắt mic giữa câu) — dừng
      // ghi nhưng KHÔNG gửi đoạn dở đó đi, tránh gửi câu nói bị cắt ngang không trọn ý.
      if (recorderRef.current) {
        suppressNextRef.current = true;
        recorderRef.current.stop();
      }
      setIsSpeechDetected(false);
      speechStartRef.current = null;
      silenceStartRef.current = null;
      return stopPolling;
    }

    const computeRms = (): number => {
      const analyser = analyserRef.current;
      const dataArray = dataArrayRef.current;
      if (!analyser || !dataArray) return 0;
      analyser.getFloatTimeDomainData(dataArray);
      let sumSquares = 0;
      for (let i = 0; i < dataArray.length; i += 1) {
        sumSquares += dataArray[i] * dataArray[i];
      }
      return Math.sqrt(sumSquares / dataArray.length);
    };

    const startRecording = () => {
      const stream = streamRef.current;
      if (!stream || recorderRef.current) return;
      chunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];
        recorderRef.current = null;
        const durationMs = speechStartRef.current ? Date.now() - speechStartRef.current : 0;
        speechStartRef.current = null;
        silenceStartRef.current = null;
        setIsSpeechDetected(false);
        const suppressed = suppressNextRef.current;
        suppressNextRef.current = false;
        if (!suppressed && durationMs >= MIN_UTTERANCE_MS && blob.size > 0) {
          void onUtteranceRef.current(blob);
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      speechStartRef.current = Date.now();
    };

    const poll = () => {
      const isLoud = computeRms() > SPEECH_RMS_THRESHOLD;

      if (!recorderRef.current) {
        if (isLoud) {
          setIsSpeechDetected(true);
          startRecording();
        }
        return;
      }

      if (isLoud) {
        silenceStartRef.current = null;
        setIsSpeechDetected(true);
        return;
      }
      if (silenceStartRef.current === null) {
        silenceStartRef.current = Date.now();
      } else if (Date.now() - silenceStartRef.current >= SILENCE_HANGOVER_MS) {
        recorderRef.current.stop();
      }
    };

    pollHandleRef.current = window.setInterval(poll, POLL_INTERVAL_MS);
    return stopPolling;
  }, [active]);

  return { isSpeechDetected };
}
