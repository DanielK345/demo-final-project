import React, { useState } from "react";
import { Bot, User, ChevronDown, ChevronUp, Cpu } from "lucide-react";
import { cn } from "@/utils/cn";
import type { ChatMessage } from "../types";

export const MessageBubble: React.FC<{ message: ChatMessage }> = ({ message }) => {
  const [showAnalysis, setShowAnalysis] = useState(false);
  const isUser = message.sender === "user";

  return (
    <div
      className={cn(
        "flex gap-3 max-w-[85%] sm:max-w-[75%]",
        isUser ? "ml-auto flex-row-reverse" : "mr-auto"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold shadow-md",
          isUser
            ? "bg-emerald-600 text-white"
            : "bg-gradient-to-tr from-cyan-600 to-emerald-600 text-white"
        )}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Message Box */}
      <div className="flex flex-col gap-1.5">
        <div
          className={cn(
            "p-4 rounded-2xl text-sm leading-relaxed shadow-lg border",
            isUser
              ? "bg-emerald-600/90 text-white border-emerald-500/50 rounded-tr-xs"
              : "bg-slate-900/90 text-slate-100 border-slate-800 rounded-tl-xs"
          )}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>

          {/* AI Internal Analysis Expandable Box */}
          {!isUser && message.analysis && (
            <div className="mt-3 pt-2.5 border-t border-slate-800/80">
              <button
                type="button"
                onClick={() => setShowAnalysis(!showAnalysis)}
                className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                <Cpu className="w-3.5 h-3.5" />
                <span>LangGraph Thought Process</span>
                {showAnalysis ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
              </button>

              {showAnalysis && (
                <div className="mt-2 p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] font-mono text-slate-400 leading-normal">
                  {message.analysis}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <span
          className={cn(
            "text-[10px] text-slate-500 px-1",
            isUser ? "text-right" : "text-left"
          )}
        >
          {message.timestamp}
        </span>
      </div>
    </div>
  );
};
