# Model License Documentation

## Zipformer Vietnamese ASR

**Model**: `hynt/Zipformer-30M-RNNT-Streaming-6000h`  
**Source**: https://huggingface.co/hynt/Zipformer-30M-RNNT-Streaming-6000h  
**Base**: k2-fsa/sherpa-onnx compatible Zipformer2

### License

⚠️ **Review the HuggingFace model card carefully before production use.**

The underlying k2-fsa/icefall Zipformer models are typically licensed under **Apache 2.0**.
Training data (6000h Vietnamese) may have additional restrictions.

**Before commercial deployment**:
1. Read the full license at: https://huggingface.co/hynt/Zipformer-30M-RNNT-Streaming-6000h
2. Confirm commercial use is permitted
3. Check if attribution is required
4. Document your compliance decision here

### sherpa-onnx

**License**: Apache 2.0  
**Source**: https://github.com/k2-fsa/sherpa-onnx

### Silero VAD

**License**: MIT  
**Source**: https://github.com/snakers4/silero-vad

## Cloud AI Providers

| Provider | Model | License |
|---|---|---|
| OpenAI | gpt-4o-transcribe | Commercial API — per OpenAI ToS |
| OpenAI | gpt-4.1-mini | Commercial API — per OpenAI ToS |
| OpenAI | gpt-4o-mini-tts | Commercial API — per OpenAI ToS |

## Data Privacy

- Audio is processed transiently; not stored unless `LIVEKIT_RECORD_AUDIO=true`
- Transcripts may be logged if `LIVEKIT_DEBUG_TRANSCRIPTS=true` (disable in production)
- Session data stored in PostgreSQL (Supabase) — see privacy policy
