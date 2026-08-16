"""Production-oriented local Vietnamese ZipFormer ASR service."""

from src.voice.asr.zipformer.service import ZipformerASRService, get_zipformer_service

__all__ = ["ZipformerASRService", "get_zipformer_service"]
