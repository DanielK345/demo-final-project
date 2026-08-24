import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeft, BookOpen, ExternalLink, Search, ShieldAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { getCurrentPolicy, getCurrentPolicySource, type PolicyCatalog, type PolicySource } from "@/features/policies/api";

export const PoliciesPage: React.FC = () => {
  const [params] = useSearchParams();
  const [catalog, setCatalog] = useState<PolicyCatalog | null>(null);
  const [source, setSource] = useState<PolicySource | null>(null);
  const section = params.get("section");
  const initialQuery = section === "privacy" ? "dữ liệu" : section === "cookies" ? "cookie" : "";
  const [query, setQuery] = useState(initialQuery);
  const [error, setError] = useState<string | null>(null);
  const [showSource, setShowSource] = useState(false);

  useEffect(() => {
    getCurrentPolicy().then(setCatalog).catch((cause) => setError(cause instanceof Error ? cause.message : "Không thể tải chính sách."));
  }, []);

  const loadSource = async () => {
    setShowSource(true);
    if (source) return;
    try { setSource(await getCurrentPolicySource()); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Không thể tải bản nguồn."); }
  };

  const rules = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("vi-VN");
    if (!catalog || !normalized) return catalog?.operational_rules ?? [];
    return catalog.operational_rules.filter((rule) => `${rule.title} ${rule.content} ${rule.category} ${rule.citation}`.toLocaleLowerCase("vi-VN").includes(normalized));
  }, [catalog, query]);

  return (
    <main className="min-h-screen bg-[#F5FAFA] px-4 py-8 dark:bg-[#0B0E11]">
      <div className="mx-auto max-w-5xl">
        <Link to="/" className="inline-flex items-center gap-2 text-sm font-bold text-[#008F88]"><ArrowLeft className="h-4 w-4" />Quay lại AloSM</Link>
        <header className="mt-5 rounded-[30px] bg-[#173132] p-7 text-white">
          <BookOpen className="h-8 w-8 text-[#00C9B7]" />
          <h1 className="mt-4 text-3xl font-extrabold">Điều khoản và chính sách AloSM</h1>
          <p className="mt-2 text-sm text-white/70">Catalog vận hành đã được chủ dự án phê duyệt, có version, nguồn và citation.</p>
          {catalog && <p className="mt-3 text-xs font-bold text-[#82FFF1]">Phiên bản {catalog.catalog_version} · hiệu lực {new Date(catalog.effective_from).toLocaleDateString("vi-VN")}</p>}
        </header>

        {error && <p role="alert" className="mt-4 rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{error}</p>}
        {catalog && <section className="mt-5 rounded-3xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200"><div className="flex gap-3"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" /><div><strong>Phạm vi pháp lý của nguồn</strong><p className="mt-1 leading-6">{catalog.legal_notice}</p><p className="mt-2 text-xs">SHA-256: <code className="break-all">{catalog.source_sha256}</code></p></div></div></section>}

        <label className="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 dark:border-white/10 dark:bg-white/5"><Search className="h-5 w-5 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Tìm: hoàn tiền, dữ liệu cá nhân, hủy chuyến..." className="w-full bg-transparent text-sm outline-none dark:text-white" /></label>

        <section className="mt-5 grid gap-3 md:grid-cols-2">
          {rules.map((rule) => <article key={rule.id} id={rule.id} className="rounded-3xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/5"><span className="rounded-full bg-[#E7FBF9] px-2.5 py-1 text-[10px] font-extrabold uppercase text-[#008F88]">{rule.category}</span><h2 className="mt-3 font-extrabold text-[#173132] dark:text-white">{rule.title}</h2><p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{rule.content}</p><p className="mt-3 text-xs text-slate-400">Nguồn: {rule.citation}</p></article>)}
        </section>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/5">
          <button type="button" onClick={() => void loadSource()} className="inline-flex items-center gap-2 rounded-xl bg-[#173132] px-4 py-2 text-sm font-bold text-white"><ExternalLink className="h-4 w-4" />Xem toàn bộ bản nguồn nguyên vẹn</button>
          {showSource && <div className="mt-4 max-h-[65vh] overflow-auto rounded-2xl bg-slate-50 p-4 dark:bg-black/20"><pre className="whitespace-pre-wrap break-words font-sans text-xs leading-6 text-slate-700 dark:text-slate-300">{source?.content ?? "Đang tải..."}</pre></div>}
        </section>
      </div>
    </main>
  );
};
