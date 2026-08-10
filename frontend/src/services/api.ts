/**
 * services/api.ts
 * Chứa các hàm gọi HTTP API (FastAPI Backend).
 * Developer 3 sẽ hoàn thiện logic fetch/axios ở đây.
 * QUY TẮC: Thêm hàm mới bên dưới, không xóa hàm cũ.
 */

import { BookingDetails, HandoffPackage } from '../types';

const API_BASE_URL = 'http://localhost:8000/api/v1';

/**
 * Gửi yêu cầu đặt xe chính thức
 */
export async function confirmBooking(bookingData: BookingDetails): Promise<{ success: boolean; bookingId?: string }> {
  console.log('Sending booking request to API:', bookingData);
  // TODO: Implement fetch logic
  return { success: true, bookingId: 'BOOKING-' + Date.now() };
}

/**
 * Lấy danh sách các cuộc gọi đang chờ Handoff
 */
export async function getHandoffQueue(): Promise<HandoffPackage[]> {
  console.log('Fetching handoff queue...');
  // TODO: Implement fetch logic
  return [];
}

/**
 * Tiếp nhận cuộc gọi Handoff từ phía Operator
 */
export async function acceptHandoff(callId: string): Promise<boolean> {
  console.log('Accepting handoff call:', callId);
  // TODO: Implement fetch logic
  return true;
}
