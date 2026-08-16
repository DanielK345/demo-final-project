import React, { useEffect, useMemo, useState } from "react";
import { BadgePercent, Bike, Car, Check, ChevronRight, Clock3, LocateFixed, MapPin, Navigation, Sparkles, Tag, Users } from "lucide-react";
import type { BookingProgress } from "@/features/ride/api";
import { formatFare, vehicleLabel } from "@/features/ai-assistant/bookingLabels";

type View = "map" | "vehicles" | "offers";
type Props = { progress: BookingProgress | null; onSay: (message: string) => Promise<void>; disabled?: boolean; voiceCommand?: string };

const vehicles = [
  { type: "MOTORBIKE", name: "AloSM Bike", seats: 1, eta: 3, factor: .58, icon: Bike, detail: "Nhanh, linh hoạt" },
  { type: "CAR_4", name: "AloSM Car", seats: 4, eta: 4, factor: 1, icon: Car, detail: "Tiện nghi, giá tốt" },
  { type: "CAR_7", name: "AloSM Plus", seats: 7, eta: 7, factor: 1.42, icon: Car, detail: "Rộng rãi cho cả nhóm" },
] as const;

const vouchers = [
  { code: "ALO20", name: "Giảm 20% chuyến xe", percent: 20, cap: 30000, min: 80000 },
  { code: "XANH15", name: "Ưu đãi di chuyển xanh", percent: 15, cap: 20000, min: 50000 },
  { code: "FREESHIP10", name: "Giảm ngay 10.000đ", percent: 0, cap: 10000, min: 30000 },
];

function voucherSaving(voucher: typeof vouchers[number], fare: number) {
  if (fare < voucher.min) return 0;
  return voucher.percent ? Math.min(Math.round(fare * voucher.percent / 100), voucher.cap) : voucher.cap;
}

export const RideBookingExperience: React.FC<Props> = ({ progress, onSay, disabled, voiceCommand }) => {
  const inferredView: View = progress?.missing_field === "vehicle_type" ? "vehicles" : progress?.fare_amount ? "offers" : "map";
  const [view, setView] = useState<View>(inferredView);
  const [selectedVoucher, setSelectedVoucher] = useState<string | null>(null);
  const fare = progress?.fare_amount ?? 0;
  const rankedVouchers = useMemo(() => vouchers.map((item) => ({ ...item, saving: voucherSaving(item, fare) })).sort((a, b) => b.saving - a.saving), [fare]);
  const bestVoucher = rankedVouchers[0];

  useEffect(() => { setView(inferredView); }, [inferredView]);
  useEffect(() => { if (bestVoucher.saving > 0) setSelectedVoucher(bestVoucher.code); }, [bestVoucher.code, bestVoucher.saving]);
  useEffect(() => {
    const command = voiceCommand?.toLocaleLowerCase("vi-VN") ?? "";
    if (!command) return;
    if (command.includes("bản đồ") || command.includes("điểm đón") || command.includes("điểm đến")) setView("map");
    if (command.includes("loại xe") || command.includes("chọn xe")) setView("vehicles");
    if (command.includes("voucher") || command.includes("ưu đãi") || command.includes("bảng giá")) setView("offers");
    const spokenVoucher = rankedVouchers.find((voucher) => command.includes(voucher.code.toLocaleLowerCase("vi-VN")));
    if (spokenVoucher?.saving) setSelectedVoucher(spokenVoucher.code);
    if ((command.includes("hời nhất") || command.includes("tốt nhất")) && bestVoucher.saving) setSelectedVoucher(bestVoucher.code);
  }, [voiceCommand, rankedVouchers, bestVoucher.code, bestVoucher.saving]);

  const choosePlace = (kind: "pickup" | "destination", label?: string) => {
    const sentence = label
      ? kind === "pickup" ? `Điểm đón của tôi là ${label}.` : `Điểm đến của tôi là ${label}.`
      : kind === "pickup" ? "Tôi muốn chọn điểm đón." : "Tôi muốn chọn điểm đến.";
    void onSay(sentence);
  };
  const chooseVehicle = (type: string) => void onSay(`Tôi chọn ${vehicleLabel(type)}.`);

  return (
    <section className="w-full overflow-hidden rounded-[26px] border border-slate-200/80 bg-[#F5FAFA] text-left shadow-sm dark:border-white/10 dark:bg-white/5">
      <div className="bg-[#173132] px-3 py-2 text-center text-[9px] font-semibold text-white/75">Nói “mở bản đồ”, “chọn xe” hoặc “voucher hời nhất” để điều khiển</div>
      <div className="flex items-center gap-1 border-b border-slate-200/70 bg-white/80 p-1.5 dark:border-white/10 dark:bg-white/5">
        {([['map','Bản đồ',MapPin],['vehicles','Loại xe',Car],['offers','Ưu đãi',BadgePercent]] as const).map(([id,label,Icon]) => (
          <button key={id} type="button" onClick={() => setView(id)} className={`flex flex-1 items-center justify-center gap-1.5 rounded-2xl px-2 py-2 text-[11px] font-bold transition ${view === id ? 'bg-[#00C9B7] text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 dark:hover:bg-white/10'}`}><Icon className="h-3.5 w-3.5" />{label}</button>
        ))}
      </div>

      {view === "map" && (
        <div>
          <div className="relative h-44 overflow-hidden bg-[#EAF1F2]">
            <div className="absolute inset-0 opacity-80" style={{ backgroundImage: 'linear-gradient(30deg, transparent 46%, white 47%, white 53%, transparent 54%), linear-gradient(120deg, transparent 45%, white 46%, white 54%, transparent 55%)', backgroundSize: '90px 90px, 120px 120px' }} />
            <div className="absolute left-[12%] top-[18%] h-2 w-40 rotate-12 rounded-full bg-white" /><div className="absolute right-[3%] top-[44%] h-2 w-48 -rotate-12 rounded-full bg-white" />
            {[[22,34],[70,23],[79,68],[36,74],[56,48]].map(([x,y], index) => <span key={index} title="Xe AloSM minh họa — chưa phải fleet realtime" className="absolute grid h-8 w-8 place-items-center rounded-xl border-2 border-white bg-[#00C9B7] text-white shadow-lg" style={{ left: `${x}%`, top: `${y}%` }}>{index % 2 ? <Bike className="h-4 w-4" /> : <Car className="h-4 w-4" />}</span>)}
            <span className="absolute left-1/2 top-1/2 grid h-12 w-12 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-[#00C9B7]/20"><span className="grid h-7 w-7 place-items-center rounded-full border-4 border-white bg-[#173132] text-white shadow-xl"><LocateFixed className="h-3 w-3" /></span></span>
            <div className="absolute bottom-2 left-2 rounded-xl bg-white/90 px-2.5 py-1.5 text-[9px] font-semibold text-slate-500 shadow-sm backdrop-blur dark:bg-[#173132]/90 dark:text-slate-300">Bản đồ và xe gần đây đang là dữ liệu minh họa</div>
          </div>
          <div className="space-y-2 p-3">
            <button type="button" disabled={disabled} onClick={() => choosePlace('pickup', progress?.pickup?.label)} className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 shadow-sm disabled:opacity-50 dark:bg-white/5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-[#E7FBF9] text-[#00AFA5]"><MapPin className="h-4 w-4" /></span><span className="min-w-0 flex-1"><small className="block font-bold uppercase tracking-wider text-slate-400">Điểm đón</small><strong className="block truncate text-xs text-[#173132] dark:text-white">{progress?.pickup?.label || 'Chọn vị trí hiện tại'}</strong></span><ChevronRight className="h-4 w-4 text-slate-400" /></button>
            <button type="button" disabled={disabled} onClick={() => choosePlace('destination', progress?.destination?.label)} className="flex w-full items-center gap-3 rounded-2xl bg-white p-3 shadow-sm disabled:opacity-50 dark:bg-white/5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-amber-50 text-amber-500"><Navigation className="h-4 w-4" /></span><span className="min-w-0 flex-1"><small className="block font-bold uppercase tracking-wider text-slate-400">Điểm đến</small><strong className="block truncate text-xs text-[#173132] dark:text-white">{progress?.destination?.label || 'Chạm để chọn trên bản đồ'}</strong></span><ChevronRight className="h-4 w-4 text-slate-400" /></button>
          </div>
        </div>
      )}

      {view === "vehicles" && <div className="max-h-[310px] overflow-y-auto p-2">
        <div className="px-2 py-2"><h3 className="text-sm font-extrabold text-[#173132] dark:text-white">Xe đang ở gần bạn</h3><p className="text-[10px] text-slate-400">Danh mục minh họa; quote thật chỉ lấy từ Backend</p></div>
        {vehicles.map(({ type,name,seats,eta,factor,icon:Icon,detail }) => { const active = progress?.vehicle_type === type; const estimated = Math.max(18000, Math.round(fare * factor / 1000) * 1000); return <button key={type} type="button" disabled={disabled} onClick={() => chooseVehicle(type)} className={`mb-1 flex w-full items-center gap-3 rounded-[22px] border p-3 text-left transition disabled:opacity-50 ${active ? 'border-[#00C9B7] bg-[#E9FBF9]' : 'border-transparent bg-white hover:border-[#00C9B7]/30 dark:bg-white/5'}`}><span className="grid h-14 w-16 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-cyan-100 to-teal-50 text-[#00AFA5]"><Icon className="h-7 w-7" /></span><span className="min-w-0 flex-1"><strong className="block text-sm text-[#173132] dark:text-white">{name}</strong><span className="mt-1 flex gap-2 text-[10px] text-slate-400"><span className="flex items-center gap-1"><Users className="h-3 w-3" />{seats}</span><span className="flex items-center gap-1"><Clock3 className="h-3 w-3" />{eta} phút</span></span><small className="block truncate text-slate-400">{detail}</small></span><span className="text-right"><strong className="block text-sm text-[#173132] dark:text-white">{formatFare(estimated, progress?.currency)}</strong>{active && <span className="mt-1 inline-flex items-center gap-1 text-[9px] font-bold text-[#008F88]"><Check className="h-3 w-3" />Đã chọn</span>}</span></button> })}
      </div>}

      {view === "offers" && <div className="max-h-[310px] overflow-y-auto p-3">
        <div className="mb-3 flex items-start justify-between gap-3"><div><h3 className="text-sm font-extrabold text-[#173132] dark:text-white">Ưu đãi tốt nhất cho chuyến này</h3><p className="text-[10px] text-slate-400">Mô phỏng xếp hạng; chưa áp vào booking</p></div><Sparkles className="h-5 w-5 text-[#00C9B7]" /></div>
        <div className="space-y-2">{rankedVouchers.map((voucher,index) => { const eligible = voucher.saving > 0; const active = selectedVoucher === voucher.code; return <button key={voucher.code} type="button" disabled={!eligible} onClick={() => setSelectedVoucher(voucher.code)} className={`flex w-full items-center gap-3 rounded-[20px] border p-3 text-left disabled:opacity-45 ${active ? 'border-[#00C9B7] bg-[#E9FBF9]' : 'border-slate-200 bg-white dark:border-white/10 dark:bg-white/5'}`}><span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-amber-50 text-amber-500"><Tag className="h-5 w-5" /></span><span className="min-w-0 flex-1"><span className="flex items-center gap-2"><strong className="truncate text-xs text-[#173132] dark:text-white">{voucher.name}</strong>{index === 0 && eligible && <em className="rounded-full bg-[#00C9B7] px-2 py-0.5 text-[8px] not-italic font-bold text-white">HỜI NHẤT</em>}</span><small className="mt-1 block text-slate-400">{voucher.code} · Đơn từ {formatFare(voucher.min, 'VND')}</small></span><span className="text-right"><strong className="block text-xs text-[#008F88]">-{formatFare(voucher.saving, 'VND')}</strong>{active && <Check className="ml-auto mt-1 h-4 w-4 text-[#00C9B7]" />}</span></button> })}</div>
        <div className="mt-3 rounded-2xl bg-[#173132] p-3 text-white"><div className="flex justify-between text-[10px] text-white/60"><span>Giá dự kiến</span><span>{formatFare(fare, progress?.currency)}</span></div><div className="mt-1 flex justify-between text-sm font-extrabold"><span>Tạm tính</span><span>{formatFare(Math.max(0, fare - (rankedVouchers.find(v => v.code === selectedVoucher)?.saving ?? 0)), progress?.currency)}</span></div><p className="mt-2 text-[9px] text-white/50">Chưa có Promotion API/business rules; mã này không được gửi vào booking.</p></div>
      </div>}
    </section>
  );
};