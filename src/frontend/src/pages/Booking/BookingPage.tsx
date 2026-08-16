import React from "react";
import { Clock3, Search, Sparkles, Users } from "lucide-react";
import { MOCK_SERVICES_CATALOG } from "@/features/booking/mockData";
import { useVoiceAssistant } from "@/features/ai-assistant/context/useVoiceAssistant";

const VEHICLE_LABEL: Record<"MOTORBIKE" | "CAR_4" | "CAR_7" | "LUXURY", string> = { MOTORBIKE: "xe máy", CAR_4: "ô tô 4 chỗ", CAR_7: "ô tô 7 chỗ", LUXURY: "xe cao cấp" };

export const BookingPage: React.FC = () => {
  const { openWithPrefill, open } = useVoiceAssistant();
  return (
    <div className="mx-auto max-w-4xl space-y-6 pb-12">
      <header className="pt-2"><p className="text-xs font-bold uppercase tracking-[.18em] text-[#008F88]">Chọn dịch vụ</p><h1 className="mt-1 text-3xl font-extrabold tracking-tight text-[#173132] dark:text-white">Bạn muốn đi bằng xe nào?</h1><p className="mt-2 text-sm text-slate-500">Chọn loại xe phù hợp, trợ lý AI sẽ hoàn tất chuyến đi cùng bạn.</p></header>
      <button type="button" onClick={open} className="mobility-input flex w-full items-center gap-3 px-5 py-4 text-left"><Search className="h-5 w-5 text-[#173132]" /><span className="flex-1 text-sm font-semibold text-slate-400">Nhập điểm đến của bạn</span><Sparkles className="h-5 w-5 text-[#00C9B7]" /></button>
      <section className="mobility-card overflow-hidden p-2 sm:p-3">
        <div className="px-4 pb-2 pt-4"><h2 className="text-xl font-extrabold text-[#173132] dark:text-white">Phương tiện gần bạn</h2></div>
        <div className="space-y-2">
          {MOCK_SERVICES_CATALOG.map((service, index) => (
            <button key={service.id} type="button" onClick={() => openWithPrefill(`Tôi muốn đặt xe ${service.name} loại ${VEHICLE_LABEL[service.id]}.`)} className="group flex w-full items-center gap-4 rounded-[24px] p-3 text-left transition hover:bg-[#EFFBFA] dark:hover:bg-white/5 sm:p-4">
              <span className="h-24 w-28 shrink-0 overflow-hidden rounded-[22px] bg-gradient-to-br from-cyan-50 to-teal-100"><img src={service.image} alt="" className="h-full w-full object-cover transition group-hover:scale-105" /></span>
              <span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-3"><strong className="text-lg font-extrabold text-[#173132] dark:text-white">{service.name}</strong><strong className="whitespace-nowrap text-base text-[#173132] dark:text-white">{service.startingPrice}</strong></span><span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs font-medium text-slate-400"><span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" /> {index === 2 ? "7" : index === 0 ? "1" : "4"} khách</span><span className="flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" /> Đón trong {3 + index} phút</span></span><span className="mt-2 block line-clamp-1 text-xs text-slate-500">{service.description}</span></span>
            </button>
          ))}
        </div>
      </section>
      <section className="soft-cyan-panel rounded-[30px] p-6 sm:flex sm:items-center sm:justify-between"><div><p className="text-xs font-bold text-[#008F88]">ALO SM BUSINESS</p><h2 className="mt-2 text-2xl font-extrabold text-[#173132]">Di chuyển cho doanh nghiệp</h2><p className="mt-2 max-w-xl text-sm text-slate-500">Quản lý chuyến đi minh bạch và linh hoạt cho cả đội ngũ.</p></div><button type="button" onClick={() => openWithPrefill("Tôi cần dịch vụ xe doanh nghiệp.")} className="mt-5 rounded-2xl bg-[#00C9B7] px-6 py-3 text-sm font-extrabold text-white shadow-lg shadow-[#00C9B7]/20 sm:mt-0">Tìm hiểu ngay</button></section>
    </div>
  );
};