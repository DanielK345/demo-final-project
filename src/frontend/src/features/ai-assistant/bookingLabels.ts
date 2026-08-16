// Nhãn dùng chung giữa BookingProgressStrip (tiến trình rút gọn trong popup) và
// BookingConfirmationModal (thẻ xác nhận trước khi đặt) — tách ra 1 chỗ để 2 nơi
// luôn khớp nhau, tránh lệch nhãn nếu sửa riêng từng file. Đồng bộ với
// VehicleType và catalog bảng giá có version ở backend.
export const VEHICLE_LABELS: Record<string, string> = {
  MOTORBIKE: "Xe máy",
  CAR_4: "Ô tô 4 chỗ",
  CAR_7: "Ô tô 7 chỗ",
  LUXURY: "Xe cao cấp",
};

export function vehicleLabel(vehicleType: string | null | undefined): string {
  if (!vehicleType) return "Chưa chọn";
  return VEHICLE_LABELS[vehicleType] ?? vehicleType;
}

export function formatFare(amount: number | null | undefined, currency: string | null | undefined): string | null {
  if (amount == null) return null;
  const suffix = currency === "VND" || !currency ? "đ" : ` ${currency}`;
  return `${Math.round(amount).toLocaleString("vi-VN")}${suffix}`;
}
