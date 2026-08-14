import React from "react";
import { Briefcase, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { MOCK_SERVICES_CATALOG } from "@/features/booking/mockData";

// Nhãn loại xe theo đúng ngôn ngữ tự nhiên mà Core Agent hiểu (xem
// src/agents/booking_types.py::VehicleType.spoken_label) — dùng để soạn câu mở đầu
// hội thoại.
const VEHICLE_LABEL: Record<"MOTORBIKE" | "CAR_4" | "CAR_7", string> = {
  MOTORBIKE: "xe máy",
  CAR_4: "ô tô 4 chỗ",
  CAR_7: "ô tô 7 chỗ",
};

export const BookingPage: React.FC = () => {
  const navigate = useNavigate();

  // Trước đây bấm "Đặt ngay" mở modal tự điền pickup/dropoff rồi tự xác nhận — một
  // luồng đặt xe RIÊNG, tách khỏi Agentic AI. Theo yêu cầu, mọi nút đặt xe giờ nối
  // thẳng vào AI Assistant thay vì tự bấm: điều hướng sang /assistant kèm
  // `state.prefill`, agent tiếp quản từ đó (hỏi xác nhận, tạo booking) — chỉ còn 1
  // đường đặt xe duy nhất trong toàn app.
  const goToAssistant = (prefill: string) => {
    navigate("/assistant", { state: { prefill } });
  };

  return (
    <div className="space-y-12 pb-12">
      {/* Page Header */}
      <section className="mb-4">
        <h1 className="text-3xl md:text-4xl font-extrabold text-[#191C1E] dark:text-white mb-2 tracking-tight">
          Dịch vụ của AloSM
        </h1>
        <p className="text-base md:text-lg text-slate-500 dark:text-slate-400">
          Giải pháp di chuyển thông minh cho mọi nhu cầu
        </p>
      </section>

      {/* Service Grid Cards (3 Columns) */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {MOCK_SERVICES_CATALOG.map((service) => {
          return (
            <div
              key={service.id}
              className="bg-white rounded-2xl shadow-[0px_4px_20px_rgba(16,18,19,0.05)] border border-slate-200/60 overflow-hidden hover:shadow-[0px_8px_30px_rgba(16,18,19,0.1)] transition-all duration-300 flex flex-col justify-between dark:bg-[#12161A] dark:border-white/10"
            >
              {/* Top Image */}
              <div className="h-48 relative overflow-hidden bg-slate-100 dark:bg-white/5">
                <img
                  src={service.image}
                  alt={service.name}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
              </div>

              {/* Card Body */}
              <div className="p-6 flex flex-col flex-grow">
                <h3 className="text-xl font-bold text-[#191C1E] dark:text-white mb-2">{service.name}</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mb-6 flex-grow leading-relaxed">
                  {service.description}
                </p>

                {/* Features List */}
                <ul className="space-y-3 mb-6">
                  {service.features.map((feat, idx) => {
                    const Icon = feat.icon;
                    return (
                      <li key={idx} className="flex items-center text-xs font-semibold text-slate-600 dark:text-slate-300">
                        <Icon className="w-4 h-4 text-[#006a62] dark:text-[#00D1C1] mr-2" />
                        <span>{feat.label}</span>
                      </li>
                    );
                  })}
                </ul>

                {/* Footer Price & Booking CTA Button */}
                <div className="flex items-center justify-between mt-auto pt-4 border-t border-slate-100 dark:border-white/10">
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">Từ</p>
                    <p className="text-base font-extrabold text-[#191C1E] dark:text-white">{service.startingPrice}</p>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      goToAssistant(`Tôi muốn đặt xe ${service.name} loại ${VEHICLE_LABEL[service.id]}.`)
                    }
                    className="inline-flex items-center gap-1.5 bg-[#00D1C1] hover:bg-[#006a62] text-white font-bold text-xs px-6 py-2.5 rounded-[12px] transition-colors shadow-xs cursor-pointer"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    AI đặt xe ngay
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      {/* Business Services Banner */}
      <section className="bg-slate-100 rounded-2xl p-8 md:p-12 border border-slate-200/80 flex flex-col md:flex-row items-center justify-between dark:bg-white/5 dark:border-white/10">
        <div className="md:w-2/3 mb-6 md:mb-0 pr-0 md:pr-8">
          <h2 className="text-2xl md:text-3xl font-extrabold text-[#191C1E] dark:text-white mb-4">
            Dịch vụ doanh nghiệp
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-6 leading-relaxed">
            Quản lý chi phí di chuyển hiệu quả, minh bạch và an toàn cho toàn bộ nhân viên.
            Trải nghiệm nền tảng quản trị thông minh dành riêng cho đối tác doanh nghiệp.
          </p>
          <button
            type="button"
            className="border-2 border-[#006a62] text-[#006a62] hover:bg-[#006a62] hover:text-white font-bold text-xs px-6 py-2.5 rounded-[12px] transition-colors cursor-pointer dark:border-[#00D1C1] dark:text-[#00D1C1] dark:hover:bg-[#00D1C1] dark:hover:text-[#0B0E11]"
          >
            Tìm hiểu thêm
          </button>
        </div>

        <div className="md:w-1/3 flex justify-center">
          <div className="w-40 h-40 bg-[#00D1C1]/20 rounded-full flex items-center justify-center text-[#006a62] dark:text-[#00D1C1]">
            <Briefcase className="w-20 h-20" />
          </div>
        </div>
      </section>
    </div>
  );
};
