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
  const Icon = llmActive ? Sparkles : BrainCircuit;

  const title = llmActive
    ? `LLM đang bật (${status.llm_provider} · ${status.llm_model})`
    : status.llm_enabled
      ? "LLM được bật nhưng thiếu OPENAI_API_KEY — đang dùng rule-based"
      : "LLM đang tắt — đang dùng rule-based";

  const detail = llmActive
    ? "Web chat đang dùng Core Agent với OpenAI hiểu ngôn ngữ."
    : "Web chat dùng Core Agent với rule-based fallback (bật OPENAI_API_KEY để dùng LLM).";

  const voiceNote = status.voice_provider
    ? status.voice_tts_enabled
      ? `Voice: ${status.voice_provider} STT (${status.voice_stt_model}) + OpenAI TTS.`
      : `Voice: ${status.voice_provider} STT (${status.voice_stt_model}), TTS fallback trình duyệt.`
    : null;

  if (compact) {
    return (
      <span
        title={`${title}. ${detail}`}
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold ${
          llmActive
            ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300"
            : "bg-amber-100 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300"
        }`}
      >
        <Icon className="w-3 h-3" />
        {llmActive ? "LLM ON" : "LLM OFF"}
      </span>
    );
  }

  return (
    <div
      className={`rounded-xl border px-3 py-2 text-xs leading-5 ${
        llmActive
          ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200"
          : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"
      }`}
    >
      <p className="font-semibold flex items-center gap-1.5">
        <Icon className="w-3.5 h-3.5 shrink-0" />
        {title}
      </p>
      <p className="mt-1 opacity-90">{detail}</p>
      {voiceNote && <p className="mt-1 opacity-90">{voiceNote}</p>}
      {!llmActive && (
        <p className="mt-1 opacity-80">
          Bật trong <code className="font-mono">.env</code>:{" "}
          <code className="font-mono">AGENT_LLM_ENABLED=true</code> và{" "}
          <code className="font-mono">OPENAI_API_KEY=...</code>
        </p>
      )}
    </div>
  );
};
