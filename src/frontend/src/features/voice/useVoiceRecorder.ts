import { useCallback, useRef } from "react";

type UseVoiceRecorderOptions = {
  onRecorded: (audio: Blob) => Promise<void> | void;
  onError?: (error: Error) => void;
};

export function useVoiceRecorder({ onRecorded, onError }: UseVoiceRecorderOptions) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const isRecordingRef = useRef(false);

  const stopTracks = useCallback(() => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  }, []);

  const stopRecording = useCallback(() => {
    if (!isRecordingRef.current) return;
    mediaRecorderRef.current?.stop();
    isRecordingRef.current = false;
  }, []);

  const startRecording = useCallback(async () => {
    if (isRecordingRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      chunksRef.current = [];

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        stopTracks();
        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];
        if (blob.size === 0) {
          onError?.(new Error("Không ghi được âm thanh. Anh/chị thử lại nhé."));
          return;
        }
        try {
          await onRecorded(blob);
        } catch (error) {
          onError?.(error instanceof Error ? error : new Error("Không thể xử lý giọng nói"));
        }
      };
      recorder.onerror = () => {
        stopTracks();
        isRecordingRef.current = false;
        onError?.(new Error("Không thể ghi âm từ micro"));
      };

      mediaRecorderRef.current = recorder;
      isRecordingRef.current = true;
      recorder.start();
    } catch (error) {
      stopTracks();
      isRecordingRef.current = false;
      onError?.(error instanceof Error ? error : new Error("Không thể truy cập micro"));
    }
  }, [onError, onRecorded, stopTracks]);

  const toggleRecording = useCallback(async () => {
    if (isRecordingRef.current) {
      stopRecording();
      return;
    }
    await startRecording();
  }, [startRecording, stopRecording]);

  return {
    toggleRecording,
    stopRecording,
    isRecording: () => isRecordingRef.current,
  };
}
