import React, { useState, useEffect } from "react";
import {
  Car,
  X,
  Wallet,
  ChevronRight,
  CheckCircle2,
  Briefcase,
  MapPin,
  Clock,
  AlertCircle,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { MOCK_SERVICES_CATALOG, type ServiceOptionItem } from "@/features/booking/mockData";
import { createBookingViaForm } from "@/features/booking/api";
import { redirectToLoginIfUnauthorized } from "@/features/auth/sessionGuard";

export const BookingPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();

  // Location state passed from Assistant page or deep link
  const routeState = location.state as
    | { openModal?: boolean; pickup?: string; dropoff?: string; serviceId?: string }
    | undefined;

  const [pickup, setPickup] = useState(
    routeState?.pickup || "123 Tech Boulevard, Innovation District"
  );
  const [dropoff, setDropoff] = useState(
    routeState?.dropoff || "Terminal 1, City International Airport"
  );
  const [selectedServiceId, setSelectedServiceId] = useState<string>(
    routeState?.serviceId || "plus"
  );
  const [isModalOpen, setIsModalOpen] = useState<boolean>(routeState?.openModal ?? false);
  const [isConfirmedSuccess, setIsConfirmedSuccess] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmedFare, setConfirmedFare] = useState<number | null>(null);

  // Sync state if coming from navigation state
  useEffect(() => {
    if (routeState?.openModal) {
      setIsModalOpen(true);
      if (routeState.pickup) setPickup(routeState.pickup);
      if (routeState.dropoff) setDropoff(routeState.dropoff);
      if (routeState.serviceId) setSelectedServiceId(routeState.serviceId);
    }
  }, [routeState]);

  const selectedService: ServiceOptionItem =
    MOCK_SERVICES_CATALOG.find((s) => s.id === selectedServiceId) || MOCK_SERVICES_CATALOG[1];

  const mapBgUrl =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDe5Ap0tASk3jVQOZwE69jpAauSAkYMG0VqBTIcIpDBLkY9fSGb54iUB0rNv0GNZqkDNVDHW96-3UaSr5r99EJuUXQLbuVRJcnCcShOBTvP39FVjypCbJOobcaZb8W0DbC4cQK-BYFGts1-YUIkhSqvfEK8KJ8BItP0MSb8FhD459LVSA7iaB58t1tq67X-Z69M044eG5mEJLpjQNfAPhXSUC3j91trTIv27PCx4uD99E4TUMtZ5e5s";

  const handleOpenConfirmModal = (serviceId: "taxi" | "plus" | "premium") => {
    setSelectedServiceId(serviceId);
    setError(null);
    setIsModalOpen(true);
  };

  const handleConfirmRide = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { booking, sessionId } = await createBookingViaForm(
        pickup,
        dropoff,
        selectedServiceId as "taxi" | "plus" | "premium",
      );
      setConfirmedFare(booking.estimated_fare);
      setIsConfirmedSuccess(true);
      setTimeout(() => {
        setIsModalOpen(false);
        setIsConfirmedSuccess(false);
        navigate("/tracking", { state: { sessionId, bookingId: booking.booking_id, pickup, destination: dropoff } });
      }, 1500);
    } catch (cause) {
      if (redirectToLoginIfUnauthorized(cause, navigate)) return;
      setError(cause instanceof Error ? cause.message : "Không thể đặt xe, vui lòng thử lại.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setIsConfirmedSuccess(false);
    setError(null);
  };

  return (
    <div className="space-y-12 pb-12">
      {/* Page Header */}
      <section className="mb-4">
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] mb-2 tracking-tight">
          Dịch vụ của AloSM
        </h1>
        <p className="text-base md:text-lg text-slate-500">
          Giải pháp di chuyển thông minh cho mọi nhu cầu
        </p>
      </section>

      {/* Service Grid Cards (3 Columns) */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {MOCK_SERVICES_CATALOG.map((service) => {
          return (
            <div
              key={service.id}
              className="bg-white rounded-2xl shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/60 overflow-hidden hover:shadow-[0px_8px_30px_rgba(16,18,19,0.1)] transition-all duration-300 flex flex-col justify-between"
            >
              {/* Top Image */}
              <div className="h-48 relative overflow-hidden bg-slate-100">
                <img
                  src={service.image}
                  alt={service.name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
              </div>

              {/* Card Body */}
              <div className="p-6 flex flex-col flex-grow">
                <h3 className="text-xl font-bold text-[#191C1E] mb-2">{service.name}</h3>
                <p className="text-sm text-slate-500 mb-6 flex-grow leading-relaxed">
                  {service.description}
                </p>

                {/* Features List */}
                <ul className="space-y-3 mb-6">
                  {service.features.map((feat, idx) => {
                    const Icon = feat.icon;
                    return (
                      <li key={idx} className="flex items-center text-xs font-semibold text-slate-600">
                        <Icon className="w-4 h-4 text-[#006a62] mr-2" />
                        <span>{feat.label}</span>
                      </li>
                    );
                  })}
                </ul>

                {/* Footer Price & Booking CTA Button */}
                <div className="flex items-center justify-between mt-auto pt-4 border-t border-slate-100">
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Từ</p>
                    <p className="text-base font-extrabold text-[#191C1E]">{service.startingPrice}</p>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleOpenConfirmModal(service.id)}
                    className="bg-[#00D1C1] hover:bg-[#006a62] text-white font-bold text-xs px-6 py-2.5 rounded-[12px] transition-colors shadow-xs cursor-pointer"
                  >
                    Đặt ngay
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      {/* Business Services Banner */}
      <section className="bg-slate-100 rounded-2xl p-8 md:p-12 border border-slate-200/80 flex flex-col md:flex-row items-center justify-between">
        <div className="md:w-2/3 mb-6 md:mb-0 pr-0 md:pr-8">
          <h2 className="text-2xl md:text-3xl font-extrabold text-[#191C1E] mb-4">
            Dịch vụ doanh nghiệp
          </h2>
          <p className="text-sm text-slate-600 mb-6 leading-relaxed">
            Quản lý chi phí di chuyển hiệu quả, minh bạch và an toàn cho toàn bộ nhân viên.
            Trải nghiệm nền tảng quản trị thông minh dành riêng cho đối tác doanh nghiệp.
          </p>
          <button
            type="button"
            className="border-2 border-[#006a62] text-[#006a62] hover:bg-[#006a62] hover:text-white font-bold text-xs px-6 py-2.5 rounded-[12px] transition-colors cursor-pointer"
          >
            Tìm hiểu thêm
          </button>
        </div>

        <div className="md:w-1/3 flex justify-center">
          <div className="w-40 h-40 bg-[#00D1C1]/20 rounded-full flex items-center justify-center text-[#006a62]">
            <Briefcase className="w-20 h-20 text-[#006a62]" />
          </div>
        </div>
      </section>

      {/* CONFIRM BOOKING MODAL POPUP OVERLAY */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Blurred Background Map Backdrop */}
          <div className="fixed inset-0 z-0">
            <div
              className="absolute inset-0 bg-cover bg-center opacity-40 blur-sm scale-105"
              style={{ backgroundImage: `url('${mapBgUrl}')` }}
            />
            <div
              className="absolute inset-0 bg-slate-950/50 backdrop-blur-md transition-opacity"
              onClick={handleCloseModal}
            />
          </div>

          {/* Main Booking Modal Container */}
          <div className="relative z-10 w-full max-w-[480px] bg-white rounded-[24px] shadow-[0px_8px_32px_rgba(16,18,19,0.12)] border border-slate-200 overflow-hidden flex flex-col">
            {/* Header */}
            <div className="px-6 py-5 border-b border-slate-100 flex justify-between items-center bg-white/80 backdrop-blur-xl">
              <h2 className="text-xl font-extrabold text-[#191C1E]">Confirm Booking</h2>
              <button
                type="button"
                onClick={handleCloseModal}
                className="text-slate-400 hover:text-[#191C1E] transition-colors p-2 rounded-full hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {!isConfirmedSuccess ? (
              /* Content Body */
              <div className="p-6 flex flex-col gap-6">
                {/* Route Details */}
                <div className="relative pl-10">
                  {/* Dashed Route Line */}
                  <div
                    className="absolute left-[11px] top-6 bottom-6 w-[2px]"
                    style={{
                      background:
                        "repeating-linear-gradient(to bottom, #bacac6 0, #bacac6 4px, transparent 4px, transparent 8px)",
                    }}
                  />

                  {/* Pickup */}
                  <div className="relative z-10 mb-6">
                    <div className="absolute -left-10 top-1 w-6 h-6 rounded-full bg-white border-2 border-[#00D1C1] flex items-center justify-center shadow-xs">
                      <div className="w-2 h-2 rounded-full bg-[#00D1C1]" />
                    </div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      PICKUP
                    </p>
                    <input
                      type="text"
                      value={pickup}
                      onChange={(e) => setPickup(e.target.value)}
                      disabled={isLoading}
                      className="w-full text-sm font-bold text-[#191C1E] bg-transparent focus:outline-none focus:border-b focus:border-[#00D1C1] truncate disabled:opacity-60"
                    />
                  </div>

                  {/* Destination */}
                  <div className="relative z-10">
                    <div className="absolute -left-10 top-1 w-6 h-6 rounded-full bg-[#191C1E] flex items-center justify-center shadow-xs">
                      <MapPin className="w-3.5 h-3.5 text-white" />
                    </div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                      DESTINATION
                    </p>
                    <input
                      type="text"
                      value={dropoff}
                      onChange={(e) => setDropoff(e.target.value)}
                      disabled={isLoading}
                      className="w-full text-sm font-bold text-[#191C1E] bg-transparent focus:outline-none focus:border-b focus:border-[#00D1C1] truncate disabled:opacity-60"
                    />
                  </div>
                </div>

                {/* Service Selection Card */}
                <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 flex items-center gap-4 hover:shadow-xs transition-shadow">
                  <div className="w-16 h-16 rounded-lg bg-white flex items-center justify-center border border-slate-200 shrink-0">
                    <Car className="w-8 h-8 text-[#00D1C1]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between items-start mb-1">
                      <h3 className="text-sm font-bold text-[#191C1E]">{selectedService.name}</h3>
                      <p className="text-sm font-extrabold text-[#191C1E]">
                        Từ {selectedService.startingPrice}
                      </p>
                    </div>
                    <p className="text-xs text-slate-500 font-medium flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-[#00D1C1]" />
                      <span>Giá cuối cùng do hệ thống tính khi xác nhận</span>
                    </p>
                  </div>
                </div>

                {/* Payment Method */}
                <div className="flex flex-col gap-2">
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider pl-1">
                    PAYMENT METHOD
                  </p>
                  <div className="flex items-center justify-between p-4 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 cursor-pointer transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded bg-[#00D1C1]/20 flex items-center justify-center text-[#006a62]">
                        <Wallet className="w-5 h-5" />
                      </div>
                      <span className="text-sm font-bold text-[#191C1E]">AloSM Pay</span>
                    </div>
                    <ChevronRight className="w-5 h-5 text-slate-400" />
                  </div>
                </div>

                {error && (
                  <p className="flex items-start gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-xl p-3">
                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>{error}</span>
                  </p>
                )}

                {/* Footer Actions */}
                <div className="pt-2 flex flex-col gap-3">
                  <button
                    type="button"
                    onClick={handleConfirmRide}
                    disabled={isLoading}
                    className="w-full h-14 bg-[#00D1C1] text-white font-bold text-sm rounded-xl hover:bg-[#006a62] shadow-[0_4px_14px_rgba(0,209,193,0.3)] transition-all active:scale-[0.98] flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                  >
                    {isLoading ? <span>Đang kết nối tài xế...</span> : <span>Xác nhận đặt xe</span>}
                  </button>

                  <button
                    type="button"
                    onClick={handleCloseModal}
                    disabled={isLoading}
                    className="w-full h-12 bg-transparent text-slate-600 border border-slate-300 font-bold text-sm rounded-xl hover:bg-slate-100 transition-all active:scale-[0.98] cursor-pointer disabled:opacity-50"
                  >
                    Hủy
                  </button>
                </div>
              </div>
            ) : (
              /* Success Confirmation State */
              <div className="text-center space-y-4 py-8 px-6">
                <div className="w-16 h-16 rounded-full bg-[#00D1C1]/20 text-[#006a62] border border-[#00D1C1]/40 flex items-center justify-center mx-auto animate-bounce">
                  <CheckCircle2 className="w-10 h-10" />
                </div>
                <div>
                  <span className="text-xs font-bold text-[#006a62] uppercase tracking-widest">
                    ĐẶT XE THÀNH CÔNG
                  </span>
                  <h3 className="text-2xl font-extrabold text-[#191C1E] mt-1">
                    Đang tìm tài xế AloSM!
                  </h3>
                  {confirmedFare !== null && (
                    <p className="text-sm font-bold text-[#191C1E] mt-2">
                      Giá cước: {confirmedFare.toLocaleString("vi-VN")} ₫
                    </p>
                  )}
                  <p className="text-xs text-slate-500 mt-1">
                    Hệ thống đang chuyển bạn tới màn hình Theo Dõi Chuyến Đi (Live Tracking)...
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
