import React, { useRef, useEffect } from "react";
import { Bot, Sparkles, AlertCircle } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import type { ChatMessage } from "../types";
import { Skeleton } from "@/components/ui/Skeleton";

export interface ChatWindowProps {
  messages: ChatMessage[];
  onSendMessage: (text: string) => void;
  isLoading?: boolean;
  error?: string | null;
  agentStatus?: { status: string; agent: string };
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  onSendMessage,
  isLoading,
  error,
  agentStatus,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] rounded-2xl bg-slate-950/80 border border-slate-800 backdrop-blur-xl shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-cyan-600 flex items-center justify-center text-white shadow-md">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100">AloSM AI Copilot</h2>
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                <Sparkles className="w-2.5 h-2.5" />
                LangGraph Active
              </span>
            </div>
            <p className="text-xs text-slate-400">
              {agentStatus ? `${agentStatus.agent} • Ready` : "Kết nối FastAPI server..."}
            </p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 p-4 lg:p-6 overflow-y-auto space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4 shadow-xl">
              <Bot className="w-8 h-8" />
            </div>
            <h3 className="text-base font-bold text-slate-200 mb-1">
              Xin chào! Tôi là AloSM AI Assistant
            </h3>
            <p className="text-xs text-slate-400 max-w-sm mb-6">
              Tôi có thể giúp bạn tìm kiếm chuyến đi, dự đoán thời gian di chuyển, tra cứu dịch vụ hoặc trả lời thắc mắc.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-md w-full">
              {[
                "Tìm xe di chuyển từ Cầu Giấy đến Hoàn Kiếm",
                "Giá cước AloSM Bike hiện tại là bao nhiêu?",
                "Thời tiết Hà Nội hôm nay có thích hợp đi xe máy?",
                "Giới thiệu các dịch vụ của AloSM",
              ].map((prompt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onSendMessage(prompt)}
                  className="p-3 text-left rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 transition-all hover:border-emerald-500/40"
                >
                  "{prompt}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}

        {isLoading && (
          <div className="flex gap-3 max-w-[75%] mr-auto">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-600 to-emerald-600 flex items-center justify-center text-white shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-2 w-48">
              <Skeleton className="h-3 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input Footer */}
      <div className="p-4 border-t border-slate-800 bg-slate-950">
        <ChatInput onSend={onSendMessage} isLoading={isLoading} />
      </div>
    </div>
  );
};
