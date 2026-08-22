import React, { useEffect, useState } from "react";
import { BrainCircuit, Sparkles } from "lucide-react";
import { checkAgentStatus } from "@/features/ai-assistant/api";
import type { AgentStatusResponse } from "@/types/api";

type LlmStatusNoteProps = {
  compact?: boolean;
};

export const LlmStatusNote: React.FC<LlmStatusNoteProps> = ({ compact = false }) => {
  const [status, setStatus] = useState<AgentStatusResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    checkAgentStatus()
      .then(setStatus)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Không thể kiểm tra trạng thái LLM. Hãy chắc backend đang chạy.
      </p>
    );
  }

  if (!status) {
    return <p className="text-xs text-slate-400 dark:text-slate-500 animate-pulse">Đang kiểm tra cấu hình LLM…</p>;
  }

  const llmActive = status.understanding_mode === "openai";
  const active = Boolean(status.livekit_configured);
  const Icon = active ? Sparkles : BrainCircuit;

  const title = status.livekit_configured
    ? `LiveKit Voice Agent đã cấu hình (${status.livekit_agent_name})`
    : "LiveKit Voice Agent chưa đủ cấu hình";

  const detail = status.livekit_configured
    ? `Voice realtime: ${status.livekit_stt_model} → ${status.livekit_llm_model} → ${status.livekit_tts_model}.`
    : "Cần cấu hình LiveKit URL, API key/secret và các model trước khi gọi.";

  const textNote = llmActive
    ? `Core Agent web chat riêng vẫn dùng ${status.llm_provider} · ${status.llm_model}.`
    : "Core Agent web chat là runtime riêng và hiện đang dùng rule-based; điều này không tắt LLM của LiveKit Voice.";

  if (compact) {
    return (
      <span
        title={`${title}. ${detail}`}
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
          active
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300"
            : "bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
        }`}
      >
        <Icon className="w-3 h-3" />
        {active ? "LIVEKIT READY" : "LIVEKIT OFF"}
      </span>
    );
  }

  return (
    <div
      className={`rounded-xl border px-3 py-2 text-xs leading-5 ${
        active
          ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200"
          : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
      }`}
    >
      <p className="font-semibold flex items-center gap-1.5">
        <Icon className="w-3.5 h-3.5 shrink-0" />
        {title}
      </p>
      <p className="mt-1 opacity-90">{detail}</p>
      <p className="mt-1 opacity-90">{textNote}</p>
    </div>
  );
};
