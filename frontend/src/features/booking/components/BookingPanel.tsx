import React, { useState } from "react";
import { Sparkles, CheckCircle2, ArrowRight, ShieldCheck } from "lucide-react";
import { LocationPicker } from "./LocationPicker";
import { ServiceSelector, SERVICE_OPTIONS } from "./ServiceSelector";
import type { VehicleType } from "../types";
import { Button } from "@/components/ui/Button";

export const BookingPanel: React.FC = () => {
  const [pickup, setPickup] = useState("126 Nguyễn Trãi, Thanh Xuân, Hà Nội");
  const [destination, setDestination] = useState("Hồ Hoàn Kiếm, Lý Thái Tổ, Hà Nội");
  const [service, setService] = useState<VehicleType>("bike");
  const [step, setStep] = useState<"input" | "confirmed">("input");
  const [isLoading, setIsLoading] = useState(false);

  const selectedServiceObj = SERVICE_OPTIONS.find((s) => s.id === service) || SERVICE_OPTIONS[0];

  const handleSwap = () => {
    const temp = pickup;
    setPickup(destination);
    setDestination(temp);
  };

  const handleConfirm = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      setStep("confirmed");
    }, 1200);
  };

  if (step === "confirmed") {
    return (
      <div className="p-8 rounded-2xl bg-slate-900 border border-emerald-500/30 text-center flex flex-col items-center justify-center space-y-4 shadow-2xl">
        <div className="w-16 h-16 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/40 animate-bounce">
          <CheckCircle2 className="w-10 h-10" />
        </div>
        <div>
          <span className="text-xs font-bold text-emerald-400 uppercase tracking-widest">
            Đặt xe thành công
          </span>
          <h3 className="text-xl font-extrabold text-slate-100 mt-1">Tài xế AloSM đang đến!</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm">
            Tài xế Nguyễn Văn A (Biển số: 29A-888.88) đang di chuyển tới điểm đón của bạn.
          </p>
        </div>

        <div className="w-full p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-left text-xs space-y-2">
          <div className="flex justify-between text-slate-400">
            <span>Dịch vụ:</span>
            <span className="font-semibold text-slate-200">{selectedServiceObj.name}</span>
          </div>
          <div className="flex justify-between text-slate-400">
            <span>Thời gian tài xế đến:</span>
            <span className="font-semibold text-emerald-400">{selectedServiceObj.eta}</span>
          </div>
          <div className="flex justify-between text-slate-400">
            <span>Giá cước:</span>
            <span className="font-semibold text-slate-100">
              {selectedServiceObj.basePrice.toLocaleString("vi-VN")} đ
            </span>
          </div>
        </div>

        <Button variant="outline" size="md" onClick={() => setStep("input")} className="w-full">
          Đặt chuyến khác
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 p-6 rounded-2xl bg-slate-950/80 border border-slate-800 backdrop-blur-xl shadow-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100">Đặt xe di chuyển</h2>
          <p className="text-xs text-slate-400">Di chuyển an toàn, tiện lợi & tiết kiệm</p>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span className="font-medium">Bảo hiểm chuyến đi</span>
        </div>
      </div>

      <LocationPicker
        pickup={pickup}
        destination={destination}
        onPickupChange={setPickup}
        onDestinationChange={setDestination}
        onSwap={handleSwap}
      />

      <ServiceSelector selected={service} onSelect={setService} />

      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-slate-400">
          <Sparkles className="w-4 h-4 text-emerald-400" />
          <span>Tự động tối ưu tuyến đường bằng AI</span>
        </div>
        <span className="font-semibold text-slate-200">Khoảng 5.8 km</span>
      </div>

      <Button
        variant="primary"
        size="lg"
        isLoading={isLoading}
        onClick={handleConfirm}
        rightIcon={<ArrowRight className="w-5 h-5" />}
        className="w-full shadow-emerald-500/20"
      >
        Xác nhận đặt {selectedServiceObj.name} • {selectedServiceObj.basePrice.toLocaleString("vi-VN")} đ
      </Button>
    </div>
  );
};
