"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { DEL, GET, POST, PUT, GRADE_RU, GRADE_RU_GEN, SPEC_RU, downloadPdf, getRole, logout, photoUrl, uploadFile } from "@/lib/api";
import { Badge, Bar, Button, Card, Field, FspAchievements, GRADE_TITLE, HistoryBlock, inputCls, ruCategory } from "@/components/ui";

type Tab = "overview" | "test" | "invites" | "vacancies" | "tasks";

interface Item {
  item_id: string; title: string; body: string; options?: string[]; number: number;
}

export default function CandidatePage() {
  const router = useRouter();
  const [stage, setStage] = useState<"loading" | "profile" | "test" | "lk">("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");

  const [profile, setProfile] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [specs, setSpecs] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  const [vacancies, setVacancies] = useState<any[]>([]);
  const [myApps, setMyApps] = useState<any[]>([]);
  const [microtasks, setMicrotasks] = useState<any[]>([]);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());
  const [invTest, setInvTest] = useState<string | null>(null);

  useEffect(() => {
    try { setSeenIds(new Set(JSON.parse(localStorage.getItem("seen_invites") || "[]"))); } catch {}
  }, []);
  const markInvitesSeen = useCallback((ids: string[]) => {
    let cur: string[] = [];
    try { cur = JSON.parse(localStorage.getItem("seen_invites") || "[]"); } catch {}
    const merged = Array.from(new Set([...cur, ...ids]));
    localStorage.setItem("seen_invites", JSON.stringify(merged));
    setSeenIds(new Set(merged));
  }, []);
  const newInvites = invites.filter((i: any) =>
    ["sent", "viewed"].includes(i.status) && !seenIds.has(i.id)).length;

  const stageInit = useRef(false);
  const loadAll = useCallback(async () => {
    try {
      const [p, st, sp, inv, vac, apps, mt] = await Promise.all([
        GET("/candidate/profile"), GET("/testing/status"), GET("/testing/specializations"),
        GET("/candidate/invitations"), GET("/vacancies"), GET("/candidate/applications"),
        GET("/candidate/microtasks"),
      ]);
      setProfile(p); setStatus(st); setSpecs(sp); setInvites(inv);
      setVacancies(vac); setMyApps(apps); setMicrotasks(mt);
      setMetrics(await GET("/candidate/metrics").catch(() => []));
      if (!stageInit.current) {
        stageInit.current = true;
        const hasCategories = (st.categories || []).length > 0;
        setStage(hasCategories ? "lk" : (p?.full_name ? "test" : "profile"));
      }
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    if (getRole() !== "candidate") router.replace("/");
    loadAll();
  }, [router, loadAll]);

  const goStep = (s: "profile" | "test") => setStage(s);
  const stepBadge = (n: number, title: string, done: boolean, active: boolean, target?: "profile" | "test") => (
    <button onClick={() => target && goStep(target)}
      className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm ${active ? "bg-white text-[#5e2b8e]" : done ? "bg-emerald-500/90 text-white" : "bg-white/15 text-white"}`}>
      <span className="font-bold">{done ? "✓" : n}</span> {title}
    </button>
  );

  return (
    <main className="min-h-screen bg-gradient-to-br from-[#3b1f5e] via-[#5e2b8e] to-[#8b5cf6] p-6">
      <div className="mx-auto max-w-4xl">
        <header className="flex items-center justify-between text-white">
          <div>
            <h1 className="text-xl font-bold">Кабинет кандидата</h1>
            {status?.categories?.length > 0 && (
              <p className="text-sm opacity-90">
                Категории: {status.categories.map((c: any) => c.category).join(" · ")}
              </p>
            )}
          </div>
          <button onClick={() => { logout(); router.replace("/"); }}
            className="rounded-xl bg-white/15 px-4 py-2 text-sm">Выйти</button>
        </header>

        {stage !== "loading" && stage !== "lk" && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {stepBadge(1, "Профиль", stage !== "profile", stage === "profile", "profile")}
            <span className="text-white/60">→</span>
            {stepBadge(2, "Тестирование", false, stage === "test", "test")}
            <span className="text-white/60">→</span>
            {stepBadge(3, "Личный кабинет", false, false)}
          </div>
        )}

        {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <div className="mt-4 space-y-4">
          {stage === "profile" && (
            <>
              <p className="text-white/90 text-sm">Шаг 1. Расскажите о себе — это увидят работодатели в подборке</p>
              <ProfileTab profile={profile} status={status} specs={specs} reload={loadAll}
                onNext={async () => { setStage("test"); }} autoSave />
              <ProfileFsp profile={profile} reload={loadAll} />
            </>
          )}
          {stage === "test" && (
            <>
              <p className="text-white/90 text-sm">Шаг 2. Пройдите тестирование — по результату вы получите категорию</p>
              <TestTab profile={profile} specs={specs}
                onDone={() => { setStage("lk"); setTab("overview"); loadAll(); }} />
            </>
          )}
          {stage === "lk" && (
            <>
              <nav className="flex flex-wrap gap-2 text-sm">
                {([["overview", "Обзор"], ["test", "Тестирование"], ["invites", `Приглашения (${invites.length}${newInvites ? `, ${newInvites} новых` : ""})`],
                   ["vacancies", "Вакансии"], ["tasks", "Задачи"]] as [Tab, string][]).map(([k, label]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={`rounded-xl px-4 py-2 font-medium ${tab === k ? "bg-white text-[#5e2b8e]" : "bg-white/15 text-white"}`}>
                    {label}
                  </button>
                ))}
              </nav>
              {tab === "overview" && <OverviewTab profile={profile} status={status} metrics={metrics} invites={invites} newInvites={newInvites} specs={specs} reload={loadAll} goTest={() => setTab("test")} />}
              {tab === "test" && <TestTab profile={profile} specs={specs} startInvitation={invTest}
                onInvitationHandled={() => setInvTest(null)}
                onDone={() => { setTab("overview"); loadAll(); }} />}
              {tab === "invites" && <InvitesTab invites={invites} reload={loadAll} markSeen={markInvitesSeen}
                onEmployerTest={(id: string) => { setInvTest(id); setTab("test"); }} />}
              {tab === "vacancies" && <VacanciesTab vacancies={vacancies} myApps={myApps} reload={loadAll} />}
              {tab === "tasks" && <TasksTab tasks={microtasks} reload={loadAll} />}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function OverviewTab({ profile, status, metrics, invites, newInvites, specs, reload, goTest }: any) {
  const best = [...metrics].sort((a: any, b: any) => (b.score || 0) - (a.score || 0))[0];
  return (
    <>
      <ProfileCard profile={profile} specs={specs} reload={reload} />
      <PulseCard />
      <GrowthCard />
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[#3b1f5e]">Ваш рейтинг</h3>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => downloadPdf().catch(() => {})}>PDF-профиль</Button>
            <Button variant="ghost" onClick={goTest}>Пройти тест ещё раз</Button>
          </div>
        </div>
        {metrics.length === 0 && (
          <p className="mt-2 text-sm text-gray-500">Категория пока не присвоена — пройдите тестирование.</p>
        )}
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          {metrics.map((m: any) => {
            const isBest = best && m === best;
            return (
              <div key={m.specialization_code || m.category} className="rounded-xl bg-gray-50 p-4">
                <div className="flex items-center justify-between">
                  <Badge>{m.category || ruCategory(`${m.specialization_code} · ${m.grade}`)}</Badge>
                  <span className="text-2xl font-bold text-[#5e2b8e]">{m.score} из 100</span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  место {m.rank}-е из {m.total ?? m.candidates_in_category} · выше {m.percentile}% кандидатов категории
                  {isBest && m.integrity != null && <> · честность {Math.round(m.integrity * 100)}%</>}
                </p>
                {isBest && Array.isArray(m.breakdown) && m.breakdown.length > 0 && (
                  <div className="mt-2 grid gap-1.5">
                    {m.breakdown.map((x: any) => <Bar key={x.key || x.label} label={x.label} value={x.value} />)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
      <TestHistory />
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[#3b1f5e]">Приглашения</h3>
          <span className="text-sm text-gray-500">новых: {newInvites}</span>
        </div>
        {invites.length === 0
          ? <p className="mt-2 text-sm text-gray-500">Пока нет — работодатели увидят вас в подборке своей категории.</p>
          : invites.slice(0, 3).map((i: any) => (
            <p key={i.id} className="mt-1 text-sm">{i.company_name} · {i.salary_min?.toLocaleString("ru")}–{i.salary_max?.toLocaleString("ru")} ₽ · {i.status_ru || i.status}</p>
          ))}
      </Card>
      <ProfileFsp profile={profile} reload={() => {}} />
      <PrivacyCard profile={profile} />
    </>
  );
}

function ProfileCard({ profile, specs, reload }: any) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState<any>({ full_name: "", contacts: {}, summary: "", stack: [] });
  const [msg, setMsg] = useState("");
  const [allSkills, setAllSkills] = useState<string[]>([]);

  useEffect(() => { GET("/skills").then(setAllSkills).catch(() => {}); }, []);
  useEffect(() => {
    setForm({
      full_name: profile?.full_name || "",
      contacts: { telegram: "", phone: "", ...(profile?.contacts || {}) },
      summary: profile?.summary || "",
      stack: profile?.stack || [],
    });
  }, [profile]);

  const save = async () => {
    try {
      await PUT("/candidate/profile", {
        full_name: form.full_name,
        contacts: form.contacts,
        summary: form.summary,
        stack: form.stack,
        experience_years: profile.experience_years || 0,
      });
      setMsg("Сохранено ✓");
      setEdit(false);
      reload();
    } catch (e: any) { setMsg("Ошибка: " + e.message); }
  };
  const addSkill = (tag: string) => {
    const t = tag.trim().toLowerCase();
    if (t && !form.stack.includes(t)) setForm({ ...form, stack: [...form.stack, t] });
  };
  const removeSkill = (tag: string) =>
    setForm({ ...form, stack: form.stack.filter((x: string) => x !== tag) });

  const uploadPhoto = async (e: any) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try { await uploadFile("/candidate/photo", f); reload(); }
    catch (ex: any) { setMsg("Ошибка загрузки фото: " + ex.message); }
  };

  return (
    <Card>
      <div className="flex items-center gap-4">
        <div className="flex-1">
          {!edit ? (
            <div className="text-sm w-full">
              <p className="text-lg font-bold text-[#3b1f5e]">{profile?.full_name || "—"}{" "}
                <button className="text-xs font-medium text-[#5e2b8e] underline" onClick={() => setEdit(true)}>изменить</button></p>
              <p className="text-gray-700">{form.contacts.telegram || "— ник"}</p>
              <p className="text-gray-700">{form.contacts.phone || "— телефон"}</p>
              {profile?.photo_url && (
                <label className="mt-1 inline-block text-xs text-[#5e2b8e] underline cursor-pointer">
                  заменить фото<input type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
                </label>
              )}
              <div className="mt-3 rounded-xl bg-[#f8f5fd] p-3">
                <p className="text-xs font-semibold text-[#5e2b8e]">О себе</p>
                <p className="mt-0.5 text-sm text-[#1e1b4b]">
                  {form.summary || <span className="text-gray-400">Расскажите о себе — работодатели увидят это в подборке</span>}
                </p>
              </div>
              <div className="mt-2 rounded-xl bg-[#f8f5fd] p-3">
                <p className="text-xs font-semibold text-[#5e2b8e]">Навыки</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {form.stack.length
                    ? form.stack.map((t: string) => (
                        <span key={t} className="rounded-lg bg-white px-2.5 py-1 text-xs font-medium text-[#5e2b8e] border border-[#e5d8f7]">{t}</span>
                      ))
                    : <span className="text-sm text-gray-400">Добавьте навыки — они влияют на соответствие вакансиям</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2 w-full">
              <input className={inputCls} placeholder="Имя и фамилия" value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              <div className="grid grid-cols-2 gap-2">
                <input className={inputCls} placeholder="@ник" value={form.contacts.telegram}
                  onChange={(e) => setForm({ ...form, contacts: { ...form.contacts, telegram: e.target.value } })} />
                <input className={inputCls} placeholder="телефон" value={form.contacts.phone}
                  onChange={(e) => setForm({ ...form, contacts: { ...form.contacts, phone: e.target.value } })} />
              </div>
              <textarea className={inputCls} rows={2} placeholder="О себе" value={form.summary}
                onChange={(e) => setForm({ ...form, summary: e.target.value })} />
              <div>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {form.stack.map((t: string) => (
                    <button key={t} onClick={() => removeSkill(t)}
                      className="rounded-lg bg-[#5e2b8e] px-2.5 py-1 text-xs font-medium text-white">{t} ×</button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <select className={inputCls} value="" onChange={(e) => addSkill(e.target.value)}>
                    <option value="">+ из списка ({allSkills.length})</option>
                    {allSkills.filter((t: string) => !form.stack.includes(t))
                      .map((t: string) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <input id="lk-custom-skill" className={inputCls} placeholder="своя"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") { addSkill((e.target as HTMLInputElement).value); (e.target as HTMLInputElement).value = ""; }
                    }} />
                  <button onClick={() => {
                    const el = document.getElementById("lk-custom-skill") as HTMLInputElement;
                    addSkill(el.value); el.value = "";
                  }} className="shrink-0 rounded-xl bg-[#5e2b8e] px-3 py-2 text-sm font-medium text-white hover:bg-[#4a2172]">→</button>
                </div>
              </div>
              <div className="flex gap-2">
                <Button onClick={save}>Сохранить</Button>
                <Button variant="ghost" onClick={() => setEdit(false)}>Отмена</Button>
              </div>
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-center gap-1">
          {profile?.photo_url ? (
            <img src={photoUrl(profile.photo_url)} alt=""
              className="h-28 w-28 rounded-2xl object-cover border-2 border-[#5e2b8e]" />
          ) : (
            <label className="flex h-28 w-28 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#d8c9ee] text-xs text-gray-400 hover:border-[#5e2b8e]">
              загрузить фото
              <input type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
            </label>
          )}
          {msg && <span className="text-xs text-gray-500">{msg}</span>}
        </div>
      </div>
    </Card>
  );
}

function TestHistory() {
  const [history, setHistory] = useState<any[]>([]);
  useEffect(() => { GET("/testing/history").then(setHistory).catch(() => {}); }, []);
  if (history.length === 0) return null;
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">История тестирований</h3>
      <p className="text-xs text-gray-400">По каждой попытке; лучший результат — тот, что видят работодатели</p>
      <div className="mt-2"><HistoryBlock history={history} /></div>
    </Card>
  );
}

function PulseCard() {
  const [pulse, setPulse] = useState<any>(null);
  useEffect(() => { GET("/candidate/pulse").then(setPulse).catch(() => {}); }, []);
  if (!pulse) return null;
  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-[#3b1f5e]">Пульс профиля</h3>
        <span className="text-sm font-bold text-[#5e2b8e]">{Math.round(pulse.freshness * 100)}%</span>
      </div>
      <div className="mt-1.5 h-2 rounded-full bg-gray-100">
        <div className="h-2 rounded-full transition-all"
          style={{ width: `${pulse.freshness * 100}%`,
                   background: pulse.freshness > 0.5 ? "#10b981" : pulse.freshness > 0.25 ? "#f59e0b" : "#ef4444" }} />
      </div>
      <p className="mt-1 text-xs text-gray-500">
        {pulse.note} · остывает через {pulse.days_left} дн.
      </p>
    </Card>
  );
}

function GrowthCard() {
  const [growth, setGrowth] = useState<any>(null);
  useEffect(() => { GET("/candidate/growth").then(setGrowth).catch(() => {}); }, []);
  if (!growth?.steps?.length) return null;
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Как поднять рейтинг</h3>
      <div className="mt-2 space-y-2">
        {growth.steps.map((s: any, i: number) => (
          <div key={i} className="flex items-center justify-between rounded-xl bg-[#f8f5fd] px-3 py-2 text-sm">
            <span className="text-[#1e1b4b]">{s.action}</span>
            <span className="font-bold text-emerald-600">+{Math.round(s.delta * 100)} б.</span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-xs text-gray-400">{growth.hint}</p>
    </Card>
  );
}

function ProfileFsp({ profile, reload }: any) {
  const [fspId, setFspId] = useState("");
  const [msg, setMsg] = useState("");
  const [reg, setReg] = useState<any>(null);
  const [sig, setSig] = useState("");
  useEffect(() => { setFspId(profile?.fsp_id || ""); }, [profile]);
  useEffect(() => {
    setReg(null); setSig("");
    if (profile?.fsp_id && profile?.has_fsp)
      GET(`/fsp/registry/${profile.fsp_id}`).then(setReg).catch(() => {});
  }, [profile]);
  const linkFsp = async () => {
    try {
      const r = await POST(`/fsp/link/${fspId}`);
      setMsg(r.linked ? `Подтверждено: ${r.name}, рейтинг ФСП ${r.rating}` : r.note);
      reload();
    } catch (e: any) { setMsg(e.message); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Достижения ФСП</h3>
      <div className="mt-2 flex gap-2">
        <input className={inputCls} placeholder="FSP-2026-0001" value={fspId}
          onChange={(e) => setFspId(e.target.value)} />
        <Button onClick={linkFsp} disabled={!fspId}>Подтвердить</Button>
      </div>
      {profile?.has_fsp && <p className="mt-2 text-sm text-emerald-600">Достижения подтверждены — плюс к рейтингу ✓</p>}
      {reg?.exists && Array.isArray(reg.achievements) && reg.achievements.length > 0 && (
        <FspAchievements items={reg.achievements} />
      )}
      {reg?.exists && (
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          <button className="text-xs text-[#5e2b8e] underline"
            onClick={() => setSig(sig ? "" : reg.signature || "")}>проверить подпись</button>
          {sig && <code className="break-all font-mono text-[10px] text-gray-500">{sig}</code>}
        </div>
      )}
      {msg && <p className="mt-2 text-sm text-gray-600">{msg}</p>}
      <p className="mt-2 text-xs text-gray-400">
        Укажите ваши достижения в ФСП: введите ID участника — подтвердим их автоматически
        и добавим вам вес в подборках работодателей. Демо-ID для проверки:
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {["FSP-2026-0001", "FSP-2026-0002", "FSP-2026-0003"].map((id) => (
          <button key={id} type="button"
            className="rounded-md border border-[#c8b0e0] px-2 py-0.5 font-mono text-[11px] text-[#5e2b8e] hover:bg-[#f3ecfa]"
            onClick={() => { setFspId(id); navigator.clipboard?.writeText(id); }}>
            {id}
          </button>
        ))}
      </div>
    </Card>
  );
}

function PrivacyCard({ profile }: any) {
  const [pub, setPub] = useState(true);
  const [consent, setConsent] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => {
    setPub(profile?.is_public ?? true);
    setConsent(profile?.consent_data_processing ?? false);
  }, [profile]);
  const save = async () => {
    try {
      await PUT(`/candidate/privacy?is_public=${pub}&consent=${consent}`);
      setMsg("Сохранено ✓");
    } catch (e: any) { setMsg("Ошибка: " + e.message); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Приватность</h3>
      <label className="mt-2 flex items-center gap-2 text-sm text-[#1e1b4b]">
        <input type="checkbox" checked={pub} onChange={(e) => setPub(e.target.checked)} />
        Показывать мой профиль работодателям в подборках
      </label>
      <label className="mt-1.5 flex items-center gap-2 text-sm text-[#1e1b4b]">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        Согласие на обработку персональных данных (152-ФЗ)
      </label>
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={save}>Сохранить</Button>
        {msg && <span className="text-xs text-gray-500">{msg}</span>}
      </div>
    </Card>
  );
}

function ProfileTab({ profile, status, specs, reload, onNext, autoSave }: any) {
  const [form, setForm] = useState({
    full_name: "", contacts: { telegram: "", phone: "" }, summary: "",
    stack: [], experience_years: 0,
  });
  const [fspId, setFspId] = useState("");
  const [msg, setMsg] = useState("");

  const [allStackTags, setAllStackTags] = useState<string[]>([]);
  useEffect(() => { GET("/skills").then(setAllStackTags).catch(() => {}); }, []);

  useEffect(() => {
    if (profile) {
      setForm({
        full_name: profile.full_name || "",
        contacts: { telegram: "", phone: "", ...(profile.contacts || {}) },
        summary: profile.summary || "",
        stack: profile.stack || [],
        experience_years: profile.experience_years || 0,
      });
      setFspId(profile.fsp_id || "");
    }
  }, [profile]);

  const save = async () => {
    try {
      await PUT("/candidate/profile", {
        full_name: form.full_name,
        contacts: form.contacts,
        summary: form.summary,
        stack: form.stack,
        experience_years: Number(form.experience_years),
      });
      await PUT(`/candidate/privacy?is_public=true&consent=true`, {});
      setMsg("Профиль сохранён");
      reload();
    } catch (e: any) { setMsg(e.message); }
  };

  const addStack = (tag: string) => {
    const t = tag.trim().toLowerCase();
    if (t && !form.stack.includes(t)) setForm({ ...form, stack: [...form.stack, t] });
  };
  const removeStack = (tag: string) =>
    setForm({ ...form, stack: form.stack.filter((x: string) => x !== tag) });

  const linkFsp = async () => {
    try {
      const r = await POST(`/fsp/link/${fspId}`);
      setMsg(r.linked ? `Связано: ${r.name}, рейтинг ФСП ${r.rating}` : r.note);
      reload();
    } catch (e: any) { setMsg(e.message); }
  };

  if (!profile) return null;
  return (
    <>
      <Card>
        <label className="flex cursor-pointer items-center justify-between rounded-xl bg-[#f8f5fd] px-4 py-3 text-sm hover:bg-[#f1e8fb]">
          <span className="text-[#3b1f5e]"><b>Загрузить резюме (PDF)</b> — распознаем имя, контакты и навыки автоматически</span>
          <span className="rounded-xl bg-[#5e2b8e] px-3 py-1.5 font-medium text-white">Выбрать файл</span>
          <input type="file" accept="application/pdf" className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              try {
                const r = await uploadFile("/candidate/resume", f);
                setForm((s: any) => ({
                  ...s,
                  full_name: r.parsed.full_name || s.full_name,
                  contacts: { ...s.contacts, ...(r.parsed.contacts || {}) },
                  stack: Array.from(new Set([...(s.stack || []), ...(r.parsed.stack || [])])),
                }));
                setMsg("Резюме распознано — проверьте данные и сохраните");
              } catch (ex: any) { setMsg("Ошибка: " + ex.message); }
            }} />
        </label>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Field label="ФИО">
            <input className={inputCls} value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </Field>
          <Field label="Telegram / телефон (контакты)">
            <input className={inputCls} placeholder="@nickname"
              value={form.contacts.telegram || ""}
              onChange={(e) => setForm({ ...form, contacts: { ...form.contacts, telegram: e.target.value } })} />
          </Field>
          <Field label="Выберите навыки">
            <div className="flex flex-wrap gap-1.5 mb-2">
              {form.stack.map((t: string) => (
                <button key={t} onClick={() => removeStack(t)}
                  className="rounded-full bg-[#5e2b8e] px-3 py-1 text-xs font-medium text-white">
                  {t} ×
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <select className={inputCls} value=""
                onChange={(e) => addStack(e.target.value)}>
                <option value="">+ из списка ({allStackTags.length})</option>
                {allStackTags.filter((t: string) => !form.stack.includes(t))
                  .map((t: string) => <option key={t} value={t}>{t}</option>)}
              </select>
              <input id="custom-skill" className={inputCls} placeholder="или впишите свою"
                onKeyDown={(e) => {
                  if (e.key === "Enter") { addStack((e.target as HTMLInputElement).value); (e.target as HTMLInputElement).value = ""; }
                }} />
              <button onClick={() => {
                const el = document.getElementById("custom-skill") as HTMLInputElement;
                addStack(el.value); el.value = "";
              }}
                className="shrink-0 rounded-xl bg-[#5e2b8e] px-3 py-2 text-sm font-medium text-white hover:bg-[#4a2172]">
                →
              </button>
            </div>
          </Field>
          <Field label="Опыт, лет">
            <input className={inputCls} type="number" value={form.experience_years}
              onChange={(e) => setForm({ ...form, experience_years: Number(e.target.value) })} />
          </Field>
          <Field label="О себе">
            <textarea className={inputCls} rows={2} value={form.summary}
              onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          </Field>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={async () => {
            await save();
            if (onNext) onNext();
          }}>Сохранить{onNext ? " и продолжить" : ""}</Button>
          {msg && msg !== "Профиль сохранён" && <span className="text-sm text-gray-600">{msg}</span>}
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Согласие на обработку данных (152-ФЗ) даётся сохранением профиля. Контакты видны работодателю
          только после того, как вы приняли приглашение или откликнулись сами.
        </p>
      </Card>
    </>
  );
}

function TestTab({ profile, specs, onDone, startInvitation, onInvitationHandled }: any) {
  const [spec, setSpec] = useState("");
  const [option, setOption] = useState("");
  const [grade, setGrade] = useState("middle");
  const [codeLang, setCodeLang] = useState("python");
  const [session, setSession] = useState<any>(null);
  const [item, setItem] = useState<Item | null>(null);
  const [choice, setChoice] = useState<number | null>(null);
  const [exact, setExact] = useState("");
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [restarted, setRestarted] = useState(false);
  const [precisionSe, setPrecisionSe] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const [thetaPts, setThetaPts] = useState<{ n: number; theta: number; se: number }[]>([]);
  const [fromInvite, setFromInvite] = useState(false);
  const invStarted = useRef<string | null>(null);
  const shownAt = useRef(Date.now());
  const itemRef = useRef<any>(null);
  const startRef = useRef<() => void>(() => {});
  const away = useRef({ ms: 0, since: 0, switches: 0 });

  useEffect(() => {
    const onVis = async () => {
      if (document.hidden) {
        away.current.since = Date.now();
        away.current.switches += 1;
      } else if (away.current.since) {
        away.current.ms += Date.now() - away.current.since;
        away.current.since = 0;
        if (itemRef.current) {
          setRestarted(true);
          setItem(null);
          itemRef.current = null;
          setChoice(null);
          setExact("");
          startRef.current();
        }
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  useEffect(() => { itemRef.current = item; }, [item]);
  useEffect(() => { startRef.current = start; });

  const markShown = () => {
    shownAt.current = Date.now();
    away.current = { ms: 0, since: 0, switches: 0 };
  };

  const currentSpec = specs?.find((s: any) => s.code === spec);

  const start = async () => {
    setBusy(true); setResult(null); setErr(""); setThetaPts([]); setFromInvite(false);
    try {
      const r = await POST("/testing/survey", {
        specialization_code: spec, survey_answer: option || "—", target_grade: grade,
        code_language: codeLang,
      });
      setSession(r);
      setItem(r.first_item);
      markShown();
    } catch (e: any) { setErr("Не удалось начать тест: " + e.message); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (!startInvitation || invStarted.current === startInvitation) return;
    invStarted.current = startInvitation;
    (async () => {
      setBusy(true); setResult(null); setErr(""); setThetaPts([]);
      try {
        const r = await POST(`/testing/start-by-invitation/${startInvitation}`);
        setSession(r);
        setItem(r.first_item);
        setFromInvite(true);
        markShown();
      } catch (e: any) { setErr("Тест работодателя: " + e.message); }
      finally { setBusy(false); onInvitationHandled?.(); }
    })();
  }, [startInvitation]);

  const answer = async () => {
    setBusy(true); setErr("");
    try {
      const payload: any = {
        item_id: item!.item_id,
        time_spent_ms: Date.now() - shownAt.current,
        away_ms: away.current.ms + (away.current.since ? Date.now() - away.current.since : 0),
        tab_switches: away.current.switches,
      };
      if (item!.options) payload.choice = choice;
      else payload.value = exact;
      const r = await POST("/testing/answer", payload);
      if (r.theta != null) setThetaPts((p) => [...p, { n: p.length + 1, theta: r.theta, se: r.se }]);
      if (r.finished) {
        setResult(r);
        setItem(null);
        setSession(null);
        onDone();
      } else {
        setItem(r.next_item);
        setChoice(null);
        setExact("");
        markShown();
        setPrecisionSe(r.se);
      }
    } catch (e: any) { setErr("Ошибка ответа: " + e.message); }
    finally { setBusy(false); }
  };

  return (
    <>
      {err && <p className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{err}</p>}
      {!item && (
        <Card>
          <h3 className="font-semibold text-[#3b1f5e]">Прохождение тестирования</h3>
          <div className="mt-2 rounded-xl bg-[#f1e8fb] p-3 text-sm text-[#3b1f5e]">
            <b>Инструкция:</b> тест занимает около 10 минут, вопросов — до 12.
            Пожалуйста, не уходите со страницы во время тестирования: если уйдёте,
            тест начнётся заново с первого вопроса. Ответы уникальны при каждой
            попытке — искать их в интернете бессмысленно. Попыток можно делать
            сколько угодно, категорию подтверждает лучшая.
          </div>
          <p className="mt-1 text-xs text-gray-400">
            Опрос определяет специализацию, тест — грейд. Результат присваивает категорию, видимую работодателям.
            Можно получить категорию в нескольких направлениях — по одному на каждое.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Field label="Специализация">
              <select className={inputCls} value={spec}
                onChange={(e) => { setSpec(e.target.value); setOption(""); }}>
                <option value="">— выберите —</option>
                {specs?.map((s: any) => <option key={s.code} value={s.code}>{s.name}</option>)}
              </select>
            </Field>
            <Field label="Заявленный грейд">
              <select className={inputCls} value={grade} onChange={(e) => setGrade(e.target.value)}>
                <option value="junior">Junior</option>
                <option value="middle">Middle</option>
                <option value="senior">Senior</option>
                <option value="lead">Lead</option>
              </select>
            </Field>
          </div>
          {["backend", "frontend", "ml", "qa", "analytics", "devops"].includes(spec) && (
            <div className="mt-3">
              <p className="text-sm font-medium text-[#5e2b8e]">Язык заданий с кодом</p>
              <select className={`${inputCls} mt-1`} value={codeLang}
                onChange={(e) => setCodeLang(e.target.value)}>
                {["python", "javascript", "c++", "c#", "java"].map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          )}
          {currentSpec && (
            <div className="mt-3">
              <p className="text-sm font-medium text-[#5e2b8e]">Отрасль / направление</p>
              <div className="mt-1 flex flex-wrap gap-2 text-sm">
                {currentSpec.survey_options.map((o: string) => (
                  <button key={o} onClick={() => setOption(o)}
                    className={`rounded-xl px-3 py-1.5 ${option === o ? "bg-[#5e2b8e] text-white" : "bg-gray-100 text-[#5e2b8e]"}`}>
                    {o}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4">
            <Button onClick={start} disabled={!spec || busy}>
              {profile?.grade ? `Пройти тест на ${grade}` : "Начать тестирование"}
            </Button>
          </div>
        </Card>
      )}

      {item && (
        <Card>
          <div className="flex justify-between text-xs text-gray-400">
            <span>{fromInvite ? "Авторский тест работодателя · " : ""}{item.title}</span><span>вопрос {item.number} из 12</span>
          </div>
          <div className="mt-1">
            <div className="text-[10px] text-gray-400">
              точность оценки: {Math.max(20, Math.round(100 * (1 - (precisionSe || session?.se || 1.5) / 1.5)))}% ·
              вопросы адаптируются к вашему уровню
            </div>
            <div className="mt-0.5 h-1 rounded-full bg-gray-100">
              <div className="h-1 rounded-full bg-emerald-500 transition-all"
                style={{ width: `${Math.max(13, 100 * (1 - (precisionSe || session?.se || 1.5) / 1.5))}%` }} />
            </div>
          </div>
          {thetaPts.length > 0 && <ThetaChart pts={thetaPts} />}
          <div className="mt-3 whitespace-pre-wrap text-sm">{item.body}</div>
          <div className="mt-3 space-y-2">
            {item.options ? item.options.map((o, i) => (
              <button key={i} onClick={() => setChoice(i)}
                className={`block w-full rounded-xl px-3 py-2 text-left text-sm ${choice === i ? "bg-[#5e2b8e] text-white" : "bg-gray-100 hover:bg-gray-200"}`}>
                {o}
              </button>
            )) : (
              <input className={inputCls} value={exact} placeholder="Ответ"
                onChange={(e) => setExact(e.target.value)} />
            )}
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={answer} disabled={busy || (item.options ? choice === null : !exact)}>
              Ответить
            </Button>
            <span className="text-xs text-gray-400">
              Время и переключения вкладок фиксируются — тест проходится самостоятельно
            </span>
          </div>
        </Card>
      )}

      {restarted && !item && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">
          Вы уходили со страницы во время тестирования — тест начался заново с первого вопроса.
        </p>
      )}

      {result && (
        <Card>
          <h3 className="font-semibold text-[#3b1f5e]">Результат</h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge>{ruCategory(result.category)}</Badge>
            <span className="text-2xl font-bold text-[#5e2b8e]">Балл: {result.score} из 100</span>
          </div>
          {thetaPts.length > 0 && <ThetaChart pts={thetaPts} />}
          {result.measured_grade !== result.applied_grade && (
            <p className="mt-2 text-sm text-amber-600">Измеренный грейд: {GRADE_TITLE[result.measured_grade] || result.measured_grade}</p>
          )}
          {result.cooldown_note && <p className="mt-2 text-sm text-amber-600">{result.cooldown_note}</p>}
          {result.integrity_note && <p className="mt-2 text-sm text-amber-600">{result.integrity_note}</p>}
          {result.integrity != null && (
            <p className="mt-1 text-xs text-gray-400">Показатель честности: {Math.round(result.integrity * 100)}%</p>
          )}
          {!restarted && !fromInvite && (
            <div className="mt-3">
              <Button variant="ghost" onClick={() => { setResult(null); start(); }}>
                Пройти ещё раз (другая ветка заданий)
              </Button>
              <span className="ml-2 text-xs text-gray-400">попытки не ограничены</span>
            </div>
          )}
        </Card>
      )}
    </>
  );
}

function ThetaChart({ pts }: { pts: { n: number; theta: number; se: number }[] }) {
  const w = 300, h = 120, pad = 10;
  const vals = pts.map((p) => p.theta);
  const min = Math.min(-1, ...vals), max = Math.max(1, ...vals);
  const x = (i: number) => (pts.length === 1 ? w / 2 : pad + (i / (pts.length - 1)) * (w - 2 * pad));
  const y = (v: number) => h - pad - 14 - ((v - min) / (max - min || 1)) * (h - 2 * pad - 18);
  const last = pts[pts.length - 1];
  return (
    <div className="mt-2 rounded-xl bg-gray-50 p-2">
      <p className="text-[10px] font-medium text-[#5e2b8e]">Оценка уровня (θ) по мере ответов</p>
      <svg width={w} height={h} className="max-w-full">
        <line x1={pad} y1={h - pad - 14} x2={w - pad} y2={h - pad - 14} stroke="#d8c9ee" />
        <line x1={pad} y1={6} x2={pad} y2={h - pad - 14} stroke="#d8c9ee" />
        {pts.length > 1 && (
          <polyline points={pts.map((p, i) => `${x(i)},${y(p.theta)}`).join(" ")}
            fill="none" stroke="#5e2b8e" strokeWidth="2" strokeLinejoin="round" />
        )}
        {pts.map((p, i) => <circle key={i} cx={x(i)} cy={y(p.theta)} r="3" fill="#5e2b8e" />)}
        <text x={pad} y={h - 2} fontSize="9" fill="#6b7280">
          ответ {last.n} · нижняя ось — текущая погрешность SE = {last.se}
        </text>
      </svg>
    </div>
  );
}

function InvitesTab({ invites, reload, markSeen, onEmployerTest }: any) {
  const [err, setErr] = useState("");
  useEffect(() => {
    if (invites?.length) markSeen(invites.map((i: any) => i.id));
  }, [invites, markSeen]);
  const act = async (id: string, accept: boolean) => {
    try {
      await POST(`/candidate/invitations/${id}/decide`, undefined, { accept: String(accept) });
      reload();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Приглашения от работодателей</h3>
      {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      {invites.length === 0 && <p className="mt-2 text-sm text-gray-500">Пока пусто — работодатели увидят вас в подборке после тестирования.</p>}
      <div className="mt-3 space-y-3">
        {invites.map((i: any) => (
          <div key={i.id} className="rounded-xl bg-gray-50 p-4">
            <div className="flex justify-between">
              <b className="text-[#3b1f5e]">{i.company_name}</b>
              <Badge tone={i.status === "accepted" ? "green" : i.status === "declined" ? "gray" : "purple"}>
                {i.status_ru || i.status}
              </Badge>
            </div>
            <p className="mt-1 text-sm">{i.message}</p>
            <p className="mt-1 text-sm font-medium text-[#5e2b8e]">
              Зарплата: {i.salary_min?.toLocaleString("ru")}–{i.salary_max?.toLocaleString("ru")} ₽
            </p>
            {i.blueprint_id && ["sent", "viewed", "accepted"].includes(i.status) && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Badge tone="purple">Авторский тест работодателя</Badge>
                <Button variant="ghost" onClick={() => onEmployerTest(i.id)}>Пройти тест работодателя</Button>
              </div>
            )}
            {["sent", "viewed"].includes(i.status) && (
              <div className="mt-2 flex gap-2">
                <Button onClick={() => act(i.id, true)}>Принять</Button>
                <Button variant="danger" onClick={() => act(i.id, false)}>Отклонить</Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function VacanciesTab({ vacancies, myApps, reload }: any) {
  const [letter, setLetter] = useState("");
  const [err, setErr] = useState("");
  const apply = async (vacancyId: string) => {
    try {
      await POST("/applications", null, { vacancy_id: vacancyId, cover_letter: letter });
      setErr("");
    } catch (e: any) { setErr(e.message); }
    reload();
  };
  return (
    <>
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Вакансии</h3>
        <textarea className={`${inputCls} mt-2`} rows={2}
          placeholder="Сопроводительное письмо (необязательно) — уйдёт вместе с откликом"
          value={letter} onChange={(e) => setLetter(e.target.value)} />
        {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
        <div className="mt-3 space-y-3">
          {vacancies.map((v: any) => (
            <div key={v.id} className="rounded-xl bg-gray-50 p-4">
              <div className="flex justify-between">
                <b className="text-[#3b1f5e]">{v.title}</b>
                <span className="text-sm font-medium text-[#5e2b8e]">
                  {v.salary_min?.toLocaleString("ru")}–{v.salary_max?.toLocaleString("ru")} ₽
                </span>
              </div>
              <p className="text-xs text-gray-500">{v.company_name} · {SPEC_RU[v.specialization_code] || v.specialization_code} · от {GRADE_RU_GEN[v.min_grade] || v.min_grade}</p>
              <p className="mt-1 text-sm">{v.description}</p>
              <div className="mt-2">
          {myApps.some((a: any) => a.vacancy_id === v.id)
            ? <Button disabled>Вы откликнулись</Button>
            : <Button onClick={() => apply(v.id)}>Откликнуться</Button>}
        </div>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Мои отклики</h3>
        {myApps.length === 0 && <p className="mt-2 text-sm text-gray-500">Откликов пока нет.</p>}
        <div className="mt-2 space-y-2 text-sm">
          {myApps.map((a: any) => (
            <div key={a.id} className="flex justify-between rounded-xl bg-gray-50 px-4 py-2">
              <span>{a.vacancy_title}</span>
              <Badge tone={a.status === "accepted" ? "green" : "gray"}>{a.status_ru || a.status}</Badge>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

function TasksTab({ tasks, reload }: any) {
  const [solutions, setSolutions] = useState<Record<string, string>>({});
  const [err, setErr] = useState("");
  const submit = async (id: string, approachOnly: boolean) => {
    try {
      await POST(`/candidate/microtasks/${id}/submit?solution=${encodeURIComponent(solutions[id] || "")}&approach_only=${approachOnly}`);
      setErr("");
      reload();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Регулярные задачи от работодателей</h3>
      <p className="text-xs text-gray-400">Решение задач поддерживает профиль «тёплым» — это плюс в рейтинге.</p>
      {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      {tasks.length === 0 && <p className="mt-2 text-sm text-gray-500">Задач пока нет.</p>}
      <div className="mt-3 space-y-3">
        {tasks.map((t: any) => (
          <div key={t.id} className="rounded-xl bg-gray-50 p-4">
            <div className="flex justify-between">
              <b className="text-[#3b1f5e]">{t.title}</b>
              <Badge tone={t.status === "solved" || t.status === "approach" ? "green" : "gray"}>{t.status}</Badge>
            </div>
            <p className="mt-1 text-sm">{t.body}</p>
            {t.status === "pending" && (
              <div className="mt-2 space-y-2">
                <textarea className={inputCls} rows={2} placeholder="Решение или подход"
                  value={solutions[t.id] || ""}
                  onChange={(e) => setSolutions({ ...solutions, [t.id]: e.target.value })} />
                <div className="flex gap-2">
                  <Button onClick={() => submit(t.id, false)}>Сдать решение</Button>
                  <Button variant="ghost" onClick={() => submit(t.id, true)}>Предложить подход</Button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
