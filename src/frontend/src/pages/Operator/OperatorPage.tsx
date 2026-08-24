import React, { useCallback, useEffect, useState } from "react";
import { Headphones, LogOut, Mic, MicOff, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { LiveKitRoom, RoomAudioRenderer, useLocalParticipant } from "@livekit/components-react";
import { ApiError } from "@/app/config/api";
import { getCurrentUser } from "@/features/auth/api";
import { clearAuthSession } from "@/features/auth/storage";
import {
  acceptHandoff,
  getOperatorToken,
  listHandoffs,
  resolveHandoff,
  type HandoffRecord,
} from "@/features/operator/api";

function OperatorRoom({ handoff, onLeave }: { handoff: HandoffRecord; onLeave: () => void }) {
  const { localParticipant, isMicrophoneEnabled } = useLocalParticipant();
  const [busy, setBusy] = useState(false);

  const leave = useCallback(async () => {
    setBusy(true);
    try {
      await resolveHandoff(handoff.handoff_id);
    } finally {
      onLeave();
    }
  }, [handoff.handoff_id, onLeave]);

  return (
    <div className="flex h-full min-h-[520px] flex-col rounded-3xl bg-white p-6 shadow-xl dark:bg-slate-950">
      <RoomAudioRenderer />
      <div className="flex items-center justify-between border-b border-slate-200 pb-4 dark:border-white/10">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#008F88]">LiveKit operator</p>
          <h1 className="mt-1 text-xl font-extrabold text-slate-900 dark:text-white">Đang xử lý cuộc gọi</h1>
          <p className="text-sm text-slate-500">Handoff {handoff.handoff_id}</p>
        </div>
        <Headphones className="h-7 w-7 text-[#00A99D]" />
      </div>
      <div className="mt-5 flex-1 rounded-2xl bg-slate-50 p-4 text-sm dark:bg-white/5">
        <p className="font-semibold text-slate-800 dark:text-slate-100">{handoff.reason}</p>
        <p className="mt-2 whitespace-pre-wrap text-slate-600 dark:text-slate-300">{handoff.summary}</p>
        {handoff.context_snapshot?.summary ? (
          <p className="mt-4 rounded-xl bg-white p-3 text-slate-600 shadow-sm dark:bg-white/10 dark:text-slate-200">
            {handoff.context_snapshot.summary}
          </p>
        ) : null}
      </div>
      <div className="mt-5 flex justify-center gap-4">
        <button
          type="button"
          onClick={() => void localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
          className={`grid h-12 w-12 place-items-center rounded-full text-white ${isMicrophoneEnabled ? "bg-[#00A99D]" : "bg-slate-500"}`}
          aria-label={isMicrophoneEnabled ? "Tắt micro" : "Bật micro"}
        >
          {isMicrophoneEnabled ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void leave()}
          className="flex items-center gap-2 rounded-xl bg-rose-600 px-4 py-2 font-semibold text-white disabled:opacity-50"
        >
          <LogOut className="h-4 w-4" /> Kết thúc
        </button>
      </div>
    </div>
  );
}

export const OperatorPage: React.FC = () => {
  const navigate = useNavigate();
  const [handoffs, setHandoffs] = useState<HandoffRecord[]>([]);
  const [active, setActive] = useState<{ handoff: HandoffRecord; serverUrl: string; token: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setHandoffs(await listHandoffs());
      setError(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) {
        clearAuthSession();
        navigate("/login", { replace: true, state: { from: "/operator" } });
        return;
      }
      setError(cause instanceof Error ? cause.message : "Không tải được queue handoff");
    }
  }, [navigate]);

  useEffect(() => {
    void getCurrentUser().catch(() => undefined);
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const accept = async (handoff: HandoffRecord) => {
    setLoadingId(handoff.handoff_id);
    try {
      await acceptHandoff(handoff.handoff_id);
      const token = await getOperatorToken(handoff.handoff_id);
      setActive({ handoff: { ...handoff, status: "accepted" }, serverUrl: token.server_url, token: token.participant_token });
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Không thể nhận cuộc gọi");
      await refresh();
    } finally {
      setLoadingId(null);
    }
  };

  const switchAccount = () => {
    clearAuthSession();
    navigate("/login", { replace: true });
  };

  if (active) {
    return (
      <LiveKitRoom token={active.token} serverUrl={active.serverUrl} connect audio onDisconnected={() => setActive(null)}>
        <OperatorRoom handoff={active.handoff} onLeave={() => setActive(null)} />
      </LiveKitRoom>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#008F88]">AloSM operator</p>
          <h1 className="mt-1 text-2xl font-extrabold text-slate-900 dark:text-white">Hàng chờ tổng đài</h1>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => void refresh()} className="rounded-xl border border-slate-200 p-2 text-slate-600 dark:border-white/10 dark:text-slate-200" aria-label="Làm mới">
            <RefreshCw className="h-5 w-5" />
          </button>
          <button type="button" onClick={switchAccount} className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600 dark:border-white/10 dark:text-slate-200">
            <LogOut className="h-4 w-4" /> Đổi tài khoản
          </button>
        </div>
      </div>
      {error ? <p className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}
      {!handoffs.length ? (
        <div className="rounded-3xl bg-white p-10 text-center text-sm text-slate-500 shadow-xl dark:bg-slate-950">Chưa có yêu cầu chuyển tổng đài viên.</div>
      ) : (
        <div className="grid gap-4">
          {handoffs.map((handoff) => (
            <article key={handoff.handoff_id} className={`rounded-2xl border bg-white p-5 shadow-sm dark:bg-slate-950 ${handoff.severity === "CRITICAL" ? "border-rose-400" : "border-slate-200 dark:border-white/10"}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-bold text-slate-900 dark:text-white">{handoff.reason_code} · {handoff.queue}</p>
                  <p className="mt-1 text-sm text-slate-500">Ưu tiên {handoff.priority} · {handoff.severity}</p>
                  <p className="mt-3 text-sm text-slate-700 dark:text-slate-200">{handoff.summary}</p>
                </div>
                <button type="button" disabled={loadingId === handoff.handoff_id} onClick={() => void accept(handoff)} className="shrink-0 rounded-xl bg-[#00A99D] px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
                  {loadingId === handoff.handoff_id ? "Đang kết nối…" : "Nhận cuộc gọi"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-400">Token operator chỉ được cấp sau khi handoff được accept và chỉ join đúng LiveKit Room.</p>
    </div>
  );
};
