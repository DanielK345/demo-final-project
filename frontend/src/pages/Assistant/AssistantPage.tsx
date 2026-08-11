import React, { useState } from "react";
import {
  Send,
  Loader2,
  Bot,
  User,
  MapPin,
  CheckCircle2,
  PlaneTakeoff,
  Sparkles,
} from "lucide-react";
import type { ChatMessage } from "@/features/ai-assistant/types";
import { useSendMessage } from "@/features/ai-assistant/hooks";
import { VoiceVisualizer } from "@/features/ai-assistant/components/VoiceVisualizer";
import { NavLink } from "react-router-dom";

export const AssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "ai-sample-1",
      sender: "assistant",
      content: "Xin chào! Bạn muốn đi đâu hôm nay?",
      timestamp: "10:00",
    },
    {
      id: "user-sample-1",
      sender: "user",
      content: "Cho tôi một xe đi ra sân bay.",
      timestamp: "10:01",
    },
  ]);

  const [inputQuery, setInputQuery] = useState("");
  const [isListening, setIsListening] = useState(false);
  const sendMessageMutation = useSendMessage();

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || inputQuery).trim();
    if (!query || sendMessageMutation.isPending) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      content: query,
      timestamp: new Date().toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");

    try {
      const res = await sendMessageMutation.mutateAsync(query);
      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: "assistant",
        content: res.response,
        analysis: res.analysis,
        timestamp: new Date().toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        content: `Kết nối backend: ${err?.message || "Không thể tải phản hồi từ LangGraph."}`,
        timestamp: new Date().toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
        }),
        status: "error",
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  const handleMicClick = () => {
    setIsListening(true);
    setTimeout(() => {
      setIsListening(false);
      handleSend("Đặt cho tôi một xe AloSM Plus từ 123 Tech St, Quận 1 ra Sân bay Tân Sơn Nhất");
    }, 2500);
  };

  const staticMapBg =
    "https://lh3.googleusercontent.com/aida-public/AB6AXuDLPuGwu-tOIckIeLv_fZQ6aCynz4bqOuDc22ljS33KwU0o33VrF0JhxcrCjdA-ubVCtsWg_M9EWDNyQcDfZ4Hl-HcS4vHNHXYh-y3aSOmmJ42cWrF_M_cg2yzy5aMoFZ6tZF5E3gvE9W8_hOJMA62zgTJxx3jaeLIxFSGJFAAYZmyI5_LTOA2nDcXUVKopaBbzebXWfM_lERQ1DEDJNI-ocEzsKhV_npZwlpBFEJYyikAXoGbAIeUv";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start pb-12">
      {/* Left Column (Main AI Interaction: Voice & Chat) */}
      <div className="lg:col-span-8 space-y-6">
        {/* Top: Immersive Voice Visualizer Card */}
        <VoiceVisualizer isListening={isListening} onMicClick={handleMicClick} />

        {/* Bottom: Chat Interface Container */}
        <div className="bg-white/80 backdrop-blur-xl rounded-[24px] p-6 shadow-sm border border-slate-200/60 flex flex-col justify-between space-y-4">
          {/* Scrollable message feed */}
          <div className="space-y-4 max-h-[220px] overflow-y-auto pr-1">
            {messages.map((msg) => {
              const isUser = msg.sender === "user";
              return (
                <div
                  key={msg.id}
                  className={`flex items-start gap-3 max-w-[85%] ${
                    isUser ? "ml-auto flex-row-reverse" : "mr-auto"
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1 ${
                      isUser
                        ? "bg-slate-200 text-slate-700"
                        : "bg-[#00D1C1]/15 text-[#006a62]"
                    }`}
                  >
                    {isUser ? (
                      <User className="w-4 h-4" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                  </div>

                  <div
                    className={`p-4 text-sm leading-relaxed ${
                      isUser
                        ? "bg-[#00D1C1] text-white rounded-2xl rounded-tr-xs font-semibold shadow-xs"
                        : "bg-slate-100 text-[#191C1E] rounded-2xl rounded-tl-xs font-medium shadow-xs"
                    }`}
                  >
                    <div>{msg.content}</div>
                    {msg.analysis && (
                      <div className="mt-2 pt-2 border-t border-slate-200 text-[11px] font-mono text-slate-500">
                        {msg.analysis}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {sendMessageMutation.isPending && (
              <div className="flex items-start gap-3 max-w-[80%] mr-auto">
                <div className="w-8 h-8 rounded-full bg-[#00D1C1]/15 flex items-center justify-center text-[#006a62] shrink-0">
                  <Bot className="w-4 h-4 animate-spin" />
                </div>
                <div className="p-4 rounded-2xl bg-slate-100 text-xs text-slate-500 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-[#00D1C1]" />
                  <span>AloSM AI đang suy nghĩ...</span>
                </div>
              </div>
            )}
          </div>

          {/* Text Input Fallback Bar */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="pt-3 border-t border-slate-100 flex items-center gap-2"
          >
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              placeholder="Nhập tin nhắn..."
              className="flex-1 bg-slate-100 border-none rounded-full px-5 py-3 text-sm text-[#191C1E] focus:outline-none focus:ring-2 focus:ring-[#00D1C1] transition-all"
            />
            <button
              type="submit"
              disabled={!inputQuery.trim() || sendMessageMutation.isPending}
              className="w-11 h-11 rounded-full bg-[#00D1C1] text-white flex items-center justify-center hover:bg-[#006a62] transition-colors disabled:opacity-50 shrink-0 cursor-pointer"
              aria-label="Gửi"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>

      {/* Right Column (Contextual Booking Summary Panel) */}
      <div className="lg:col-span-4">
        <div className="bg-white rounded-[24px] p-6 shadow-sm border border-slate-200 sticky top-24 space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-[#191C1E]">Chuyến đi dự kiến</h3>
            <span className="bg-[#00D1C1]/10 text-[#006a62] px-3 py-1 rounded-full text-xs font-semibold">
              Đang tạo
            </span>
          </div>

          {/* Map Preview Placeholder */}
          <div className="w-full h-40 bg-slate-100 rounded-xl overflow-hidden relative border border-slate-200">
            <img
              src={staticMapBg}
              alt="City route preview"
              className="w-full h-full object-cover opacity-80"
            />
            {/* Pickup Marker Dot */}
            <div className="absolute top-1/2 left-1/4 w-3.5 h-3.5 bg-[#191C1E] rounded-full shadow-md -translate-x-1/2 -translate-y-1/2 border-2 border-white" />
            {/* Destination Marker Icon */}
            <div className="absolute top-1/3 right-1/4 w-5 h-5 bg-[#00D1C1] rounded-full shadow-md translate-x-1/2 -translate-y-1/2 border-2 border-white flex items-center justify-center">
              <PlaneTakeoff className="w-3.5 h-3.5 text-white" />
            </div>
            {/* Route Path Curve */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              preserveAspectRatio="none"
              viewBox="0 0 100 100"
            >
              <path
                d="M 25 50 Q 50 20 75 33"
                fill="none"
                stroke="#00D1C1"
                strokeDasharray="4 4"
                strokeWidth="2.5"
                className="opacity-80"
              />
            </svg>
          </div>

          {/* Address Timeline */}
          <div className="space-y-4 relative">
            <div className="absolute left-[11px] top-6 bottom-6 w-0.5 bg-slate-200 z-0" />

            {/* Pickup */}
            <div className="flex items-start gap-4 relative z-10">
              <div className="w-6 h-6 rounded-full bg-[#191C1E] flex items-center justify-center shrink-0 border-2 border-white mt-0.5">
                <div className="w-1.5 h-1.5 bg-white rounded-full" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">
                  Điểm đón
                </p>
                <p className="text-sm font-bold text-[#191C1E]">123 Tech St, Quận 1</p>
              </div>
            </div>

            {/* Destination */}
            <div className="flex items-start gap-4 relative z-10">
              <div className="w-6 h-6 rounded-full bg-[#00D1C1] flex items-center justify-center shrink-0 border-2 border-white mt-0.5">
                <MapPin className="w-3.5 h-3.5 text-white" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">
                  Điểm đến
                </p>
                <p className="text-sm font-bold text-[#191C1E]">Sân bay Tân Sơn Nhất</p>
              </div>
            </div>
          </div>

          {/* Pricing & Duration Estimates */}
          <div className="pt-4 border-t border-slate-100 space-y-3 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Ước tính giá</span>
              <span className="font-semibold text-[#191C1E] animate-pulse bg-slate-100 px-2.5 py-1 rounded text-xs">
                Đang tính...
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Thời gian</span>
              <span className="font-bold text-[#191C1E]">~ 35 phút</span>
            </div>
          </div>

          {/* Action Button: Navigates to /booking WITH openModal state */}
          <NavLink
            to="/booking"
            state={{
              openModal: true,
              pickup: "123 Tech St, Quận 1",
              dropoff: "Sân bay Tân Sơn Nhất",
              serviceId: "plus",
            }}
            className="block pt-2"
          >
            <button
              type="button"
              className="w-full py-3.5 bg-slate-100 hover:bg-[#006a62] hover:text-white text-slate-600 font-bold text-sm rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer shadow-xs"
            >
              <CheckCircle2 className="w-5 h-5 text-[#00D1C1]" />
              <span>Xác nhận & Đặt xe</span>
            </button>
          </NavLink>
        </div>
      </div>
    </div>
  );
};
