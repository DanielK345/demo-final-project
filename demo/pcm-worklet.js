// AudioWorkletProcessor — chuyển audio mic (Float32, sample rate gốc của
// AudioContext, thường 48kHz) thành PCM16 rồi post message ra main thread.
// Dùng AudioWorklet thay vì ScriptProcessorNode (đã deprecated) theo đúng
// khuyến nghị hiện hành — xem docs/prompt_voice_phan5_8.md Việc 3.
//
// Việc resample về 16kHz KHÔNG làm ở đây — gửi thẳng PCM16 ở sample rate gốc
// qua WebSocket, `src/voice/audio/codec.py::PCM16Resampler` ở backend lo phần
// resample (đúng vai trò đã phân chia: audio DSP là việc Phần 1, không lặp
// lại logic đó ở JS).

class PCMCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    const channel = input && input[0];
    if (channel && channel.length > 0) {
      const pcm16 = new Int16Array(channel.length);
      for (let i = 0; i < channel.length; i++) {
        const sample = Math.max(-1, Math.min(1, channel[i]));
        pcm16[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm-capture-processor", PCMCaptureProcessor);
