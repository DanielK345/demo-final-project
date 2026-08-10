/**
 * types/index.ts
 * Chứa toàn bộ Data Types và Interfaces tập trung cho phần Frontend.
 * QUY TẮC: Chỉ THÊM type mới, không xóa các type đã có.
 */

export type UIState = 'ready' | 'listening' | 'processing' | 'speaking';
export type ModalStep = 'none' | 'confirm' | 'success';

export interface TranscriptItem {
  id: number;
  role: 'ai' | 'user';
  text: string;
}

export interface BookingDetails {
  pickup: string;
  destination: string;
  vehicle: string;
  estimatedPrice?: string;
}

export interface HandoffPackage {
  call_id: string;
  reason: 'asr_failure' | 'out_of_scope' | 'api_failure' | 'user_request';
  intent: string;
  pickup?: string;
  destination?: string;
  vehicle?: string;
  summary: string;
  pending_action: string;
  transcripts?: TranscriptItem[];
}
