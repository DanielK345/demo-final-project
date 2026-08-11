import React, { useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/Button";

export interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, isLoading }) => {
  const [text, setText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSend(text.trim());
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative flex items-end gap-2">
      <div className="relative flex-1 bg-slate-900 border border-slate-800 rounded-2xl p-2 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20 transition-all shadow-xl">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Hỏi AloSM AI Copilot (VD: 'Tìm xe đi Hồ Hoàn Kiếm', 'Thời tiết hôm nay...')..."
          rows={1}
          className="w-full bg-transparent text-slate-100 placeholder:text-slate-500 text-sm px-3 py-2 focus:outline-none resize-none max-h-32 min-h-[40px]"
        />
        <div className="flex items-center justify-between px-2 pt-1 border-t border-slate-800/60">
          <span className="text-[10px] text-slate-500 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-emerald-400" />
            Nhấn Enter để gửi, Shift+Enter để xuống dòng
          </span>
          <span className="text-[10px] text-slate-500">{text.length}/5000</span>
        </div>
      </div>

      <Button
        type="submit"
        variant="primary"
        size="md"
        isLoading={isLoading}
        disabled={!text.trim() || isLoading}
        className="h-12 w-12 rounded-2xl shrink-0 p-0"
        aria-label="Gửi tin nhắn"
      >
        <Send className="w-5 h-5" />
      </Button>
    </form>
  );
};
