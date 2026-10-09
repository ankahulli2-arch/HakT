"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { DEL, GET, POST, PUT, GRADE_RU, getRole, logout, photoUrl, uploadFile } from "@/lib/api";
import { Badge, Bar, Button, Card, Field, FspAchievements, HistoryBlock, inputCls } from "@/components/ui";

type Tab = "overview" | "vacancies" | "apps" | "tests" | "invites";

const normStatus = (s?: string | null) =>
  s === "опубликован" ? "published" : s === "черновик" ? "draft" : s || "";

const findBlueprint = (v: any, bps: any[]) =>
  bps.find((b: any) => b.vacancy_id === v.id) ||
  bps.find((b: any) => b.specialization_code === v.specialization_code);

export default function EmployerPage() {
  const router = useRouter();
  const [stage, setStage] = useState<"loading" | "profile" | "vacancies" | "tests" | "lk">("loading");
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");
  const stageInit = useRef(false);

  const [profile, setProfile] = useState<any>(null);
  const [specs, setSpecs] = useState<any[]>([]);
  const [skills, setSkills] = useState<string[]>([]);
  const [vacancies, setVacancies] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [blueprints, setBlueprints] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);

  const loadAll = useCallback(async () => {
    try {
      const [p, sp, sk, vac, ap, bp, inv] = await Promise.all([
        GET("/employer/profile"), GET("/testing/specializations"), GET("/skills"),
        GET("/employer/vacancies"), GET("/employer/applications"),
        GET("/employer/tests"), GET("/employer/invitations"),
      ]);
      setProfile(p); setSpecs(sp); setSkills(sk); setVacancies(vac);
      setApps(ap); setBlueprints(bp); setInvites(inv);
      if (!stageInit.current) {
        stageInit.current = true;
        if (!p?.company_name) setStage("profile");
        else if (vac.filter((v: any) => v.is_active !== false).length === 0) setStage("vacancies");
        else if (bp.filter((b: any) => normStatus(b.status) === "published").length === 0) setStage("tests");
        else setStage("lk");
      }
    } catch (e: any) { setError(e.message); }
  }, []);

  useEffect(() => {
    if (getRole() !== "employer") router.replace("/");
    loadAll();
  }, [router, loadAll]);

  const goStep = (s: "profile" | "vacancies" | "tests") => setStage(s);
  const stepBadge = (n: number, title: string, done: boolean, active: boolean,
                     target?: "profile" | "vacancies" | "tests") => (
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
            <h1 className="text-xl font-bold">Кабинет работодателя</h1>
            {profile?.company_name && (
              <p className="text-sm opacity-90">{profile.company_name} · вакансий: {vacancies.length} · откликов: {apps.length}</p>
            )}
          </div>
          <button onClick={() => { logout(); router.replace("/"); }}
            className="rounded-xl bg-white/15 px-4 py-2 text-sm">Выйти</button>
        </header>

        {stage !== "loading" && stage !== "lk" && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {stepBadge(1, "Компания", stage !== "profile", stage === "profile", "profile")}
            <span className="text-white/60">→</span>
            {stepBadge(2, "Кого нужны", stage !== "vacancies", stage === "vacancies", "vacancies")}
            <span className="text-white/60">→</span>
            {stepBadge(3, "Тесты", stage !== "tests", stage === "tests", "tests")}
            <span className="text-white/60">→</span>
            {stepBadge(4, "Личный кабинет", false, false)}
          </div>
        )}

        {error && <p className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}

        <div className="mt-4 space-y-4">
          {stage === "profile" && (
            <>
              <p className="text-white/90 text-sm">Шаг 1. Профиль компании — кандидаты увидят, куда идут</p>
              <CompanyStep profile={profile} onDone={async () => { stageInit.current = false; await loadAll(); setStage("vacancies"); }} />
            </>
          )}
          {stage === "vacancies" && (
            <>
              <p className="text-white/90 text-sm">Шаг 2. Какие специалисты нужны — выберите направления, детали по желанию</p>
              <VacanciesStep specs={specs} setSpecs={setSpecs} skills={skills} onDone={() => { setStage("tests"); loadAll(); }} />
            </>
          )}
          {stage === "tests" && (
            <>
              <p className="text-white/90 text-sm">Шаг 3. Тесты для ваших вакансий — можно оставить автосборку, отредактировать или заменить своими вопросами</p>
              <TestsStep vacancies={vacancies} blueprints={blueprints} specs={specs}
                onDone={() => { setStage("lk"); setTab("overview"); loadAll(); }} />
            </>
          )}
          {stage === "lk" && (
            <>
              <nav className="flex flex-wrap gap-2 text-sm">
                {([["overview", "Обзор"], ["vacancies", `Вакансии и подборка (${vacancies.length})`],
                   ["apps", `Отклики (${apps.length})`], ["tests", "Тесты"],
                   ["invites", `Приглашения (${invites.length})`]] as [Tab, string][]).map(([k, label]) => (
                  <button key={k} onClick={() => setTab(k)}
                    className={`rounded-xl px-4 py-2 font-medium ${tab === k ? "bg-white text-[#5e2b8e]" : "bg-white/15 text-white"}`}>
                    {label}
                  </button>
                ))}
              </nav>
              {tab === "overview" && <OverviewTab profile={profile} vacancies={vacancies} apps={apps} invites={invites} reload={loadAll} />}
              {tab === "vacancies" && <VacanciesAndShortlistTab vacancies={vacancies} skills={skills} blueprints={blueprints} reload={loadAll} />}
              {tab === "apps" && <AppsTab apps={apps} reload={loadAll} />}
              {tab === "tests" && <TestsTab vacancies={vacancies} blueprints={blueprints} specs={specs} reload={loadAll} />}
              {tab === "invites" && <InvitesTab invites={invites} />}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function OverviewTab({ profile, vacancies, apps, invites, reload }: any) {
  return (
    <>
      <ProfileCard profile={profile} reload={reload} />
      <NeedBlock />
      <FunnelCard />
      <TopCard />
      <BlindCard profile={profile} reload={reload} />
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Итоги</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-3 text-center">
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-2xl font-bold text-[#5e2b8e]">{vacancies.filter((v: any) => v.is_active !== false).length}</p>
            <p className="text-xs text-gray-500">активных вакансий</p>
          </div>
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-2xl font-bold text-[#5e2b8e]">{apps.filter((a: any) => a.status === "sent").length}</p>
            <p className="text-xs text-gray-500">новых откликов</p>
          </div>
          <div className="rounded-xl bg-gray-50 p-4">
            <p className="text-2xl font-bold text-[#5e2b8e]">{invites.filter((i: any) => i.status === "accepted").length}</p>
            <p className="text-xs text-gray-500">принятых приглашений</p>
          </div>
        </div>
      </Card>
    </>
  );
}

function FunnelCard() {
  const [f, setF] = useState<any>(null);
  useEffect(() => { GET("/employer/funnel").then(setF).catch(() => {}); }, []);
  if (!f) return null;
  const steps = [
    { n: f.vacancies, l: "вакансии" },
    { n: f.applications, l: "откликов" },
    { n: f.invited, l: "приглашений" },
    { n: f.accepted, l: "принято" },
  ];
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Воронка найма</h3>
      <div className="mt-3 flex items-center gap-1.5">
        {steps.map((s, i) => (
          <div key={s.l} className="flex flex-1 items-center gap-1.5">
            <div className="flex-1 rounded-xl bg-gray-50 p-3 text-center">
              <p className="text-xl font-bold text-[#5e2b8e]">{s.n}</p>
              <p className="text-xs text-gray-500">{s.l}</p>
            </div>
            {i < steps.length - 1 && <span className="text-gray-300">→</span>}
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-gray-500">
        {f.accept_rate != null && <>Конверсия приглашения в договорённость — {Math.round(f.accept_rate * 100)}%{f.avg_decision_hours != null ? " · " : ""}</>}
        {f.avg_decision_hours != null && <>кандидаты отвечают в среднем за {f.avg_decision_hours < 24 ? `${f.avg_decision_hours} ч` : `${Math.round(f.avg_decision_hours / 24)} дн`}</>}
      </p>
    </Card>
  );
}

function TopCard() {
  const [specs, setSpecs] = useState<any[]>([]);
  const [spec, setSpec] = useState("");
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => {
    GET("/testing/specializations").then((r: any) => {
      setSpecs(r || []);
      if (r?.length) setSpec(r[0].code);
    }).catch(() => {});
  }, []);
  useEffect(() => {
    if (spec) GET(`/leaderboard/${spec}`).then((r: any) => setItems(r.items || [])).catch(() => {});
  }, [spec]);
  if (items.length === 0) return null;
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="font-semibold text-[#3b1f5e]">Топ категории</h3>
          <p className="mt-1 text-xs text-gray-500">Живой рейтинг по итогам CAT-тестов — кого звать на собеседование</p>
        </div>
        <select className={`${inputCls} w-auto shrink-0`} value={spec} onChange={(e) => setSpec(e.target.value)}>
          {specs.map((s: any) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </div>
      <div className="mt-2 grid gap-1">
        {items.slice(0, 8).map((x: any) => (
          <div key={x.rank} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-1.5 text-sm">
            <span>{x.rank}. {x.name} <span className="text-gray-400">· {GRADE_RU[x.grade] || x.grade}</span></span>
            <span className="font-semibold text-[#5e2b8e]">{x.score} из 100</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function BlindCard({ profile, reload }: any) {
  const [busy, setBusy] = useState(false);
  const on = !!profile?.blind_mode;
  const toggle = async () => {
    setBusy(true);
    try {
      await PUT(`/employer/blind?enabled=${!on}`);
      reload?.();
    } finally { setBusy(false); }
  };
  return (
    <Card className={on ? "border-2 border-[#5e2b8e]" : ""}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="font-semibold text-[#3b1f5e]">Слепой найм</h3>
          <p className="mt-1 text-sm text-gray-500">
            В подборках кандидаты показаны без имён и фото — оцениваете только категорию, стек и честность теста.
            Личность открывается после принятия приглашения.
          </p>
        </div>
        <button onClick={toggle} disabled={busy}
          aria-label="Слепой найм"
          className={`relative h-7 w-12 shrink-0 rounded-full transition ${on ? "bg-[#5e2b8e]" : "bg-gray-300"}`}>
          <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all ${on ? "left-[22px]" : "left-0.5"}`} />
        </button>
      </div>
    </Card>
  );
}

function NeedBlock() {
  const [text, setText] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true); setErr("");
    const t0 = performance.now();
    try {
      const r = await POST("/matching/need", { raw_text: text });
      setRes({ ...r, _client_ms: Math.round(performance.now() - t0) });
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Опишите потребность текстом</h3>
      <p className="text-xs text-gray-400">Свободный текст — разберём требования и подберём кандидатов</p>
      <textarea className={`${inputCls} mt-2`} rows={3}
        placeholder="Например: нужен бэкенд-разработчик с опытом от 3 лет, Python/FastAPI, PostgreSQL, задачи про highload"
        value={text} onChange={(e) => setText(e.target.value)} />
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={run} disabled={busy || !text.trim()}>{busy ? "Подбираем…" : "Подобрать кандидатов"}</Button>
        {res && <Badge tone="green">подборка за {res.elapsed_ms ?? res._client_ms} мс</Badge>}
      </div>
      {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      {res?.parsed && (
        <p className="mt-2 flex flex-wrap gap-1.5 text-xs text-gray-600">
          {[res.parsed.specialization_code, res.parsed.min_grade && `от ${res.parsed.min_grade}`,
            ...(res.parsed.stack || [])].filter(Boolean).map((x: string, i: number) => (
            <span key={i} className="rounded-full bg-[#f1e8fb] px-2 py-0.5 text-[#5e2b8e]">{x}</span>
          ))}
        </p>
      )}
      {res?.items && <ShortlistItems items={res.items} />}
    </Card>
  );
}

function ProfileCard({ profile, reload }: any) {
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState<any>({});
  const [msg, setMsg] = useState("");

  useEffect(() => { setForm({ ...profile }); }, [profile]);

  const save = async () => {
    try {
      await PUT("/employer/profile", {
        company_name: form.company_name,
        description: form.description || "",
        industry: form.industry || "",
        contact_email: form.contact_email || "",
        contact_phone: form.contact_phone || "",
      });
      setMsg("Сохранено ✓");
      setEdit(false);
      reload();
    } catch (e: any) { setMsg("Ошибка: " + e.message); }
  };

  const uploadPhoto = async (e: any) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try { await uploadFile("/employer/photo", f); reload(); }
    catch (ex: any) { setMsg("Ошибка загрузки логотипа: " + ex.message); }
  };

  return (
    <Card>
      <div className="flex items-center gap-4">
        <div className="flex-1">
          {!edit ? (
            <div className="text-sm w-full">
              <p className="text-lg font-bold text-[#3b1f5e]">{profile?.company_name || "—"}{" "}
                <button className="text-xs font-medium text-[#5e2b8e] underline" onClick={() => setEdit(true)}>изменить</button></p>
              <p className="text-gray-700">{profile?.industry || "— сфера"}</p>
              <p className="text-gray-700">{profile?.contact_phone || "— телефон"}</p>
              {profile?.photo_url && (
                <label className="mt-1 inline-block text-xs text-[#5e2b8e] underline cursor-pointer">
                  заменить логотип<input type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
                </label>
              )}
              <div className="mt-3 rounded-xl bg-[#f8f5fd] p-3">
                <p className="text-xs font-semibold text-[#5e2b8e]">О компании</p>
                <p className="mt-0.5 text-sm text-[#1e1b4b]">
                  {form.description || <span className="text-gray-400">Расскажите о команде и продукте</span>}
                </p>
                <p className="mt-1 text-xs text-gray-500">{form.contact_email}</p>
              </div>
            </div>
          ) : (
            <div className="space-y-2 w-full">
              <input className={inputCls} placeholder="Название компании" value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
              <input className={inputCls} placeholder="Сфера деятельности" value={form.industry || ""}
                onChange={(e) => setForm({ ...form, industry: e.target.value })} />
              <textarea className={inputCls} rows={2} placeholder="О компании" value={form.description || ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })} />
              <div className="grid grid-cols-2 gap-2">
                <input className={inputCls} placeholder="телефон" value={form.contact_phone || ""}
                  onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
                <input className={inputCls} placeholder="email" value={form.contact_email || ""}
                  onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
              </div>
              <div className="flex gap-2">
                <Button onClick={save}>Сохранить</Button>
                <Button variant="ghost" onClick={() => setEdit(false)}>Отмена</Button>
              </div>
              {msg && <span className="text-xs text-gray-500">{msg}</span>}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-center gap-1">
          {profile?.photo_url ? (
            <img src={photoUrl(profile.photo_url)} alt=""
              className="h-28 w-28 rounded-2xl object-cover border-2 border-[#5e2b8e]" />
          ) : (
            <label className="flex h-28 w-28 shrink-0 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#d8c9ee] text-xs text-gray-400 hover:border-[#5e2b8e]">
              загрузить логотип
              <input type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
            </label>
          )}
          {msg && <span className="text-xs text-gray-500">{msg}</span>}
        </div>
      </div>
    </Card>
  );
}

function CompanyStep({ profile, onDone }: any) {
  const [form, setForm] = useState<any>({ company_name: "", description: "", industry: "", contact_email: "", contact_phone: "" });
  const [msg, setMsg] = useState("");

  useEffect(() => { if (profile) setForm({ ...profile }); }, [profile]);

  const save = async () => {
    try {
      await PUT("/employer/profile", {
        company_name: form.company_name,
        description: form.description || "",
        industry: form.industry || "",
        contact_email: form.contact_email || "",
        contact_phone: form.contact_phone || "",
      });
      onDone();
    } catch (e: any) { setMsg(e.message); }
  };

  const uploadPhoto = async (e: any) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try { await uploadFile("/employer/photo", f); }
    catch (ex: any) { setMsg("Ошибка загрузки логотипа: " + ex.message); }
  };

  return (
    <>
      <Card>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Название компании">
            <input className={inputCls} placeholder="Название компании" value={form.company_name || ""}
              onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
          </Field>
          <Field label="Сфера деятельности">
            <input className={inputCls} placeholder="Сфера деятельности" value={form.industry || ""}
              onChange={(e) => setForm({ ...form, industry: e.target.value })} />
          </Field>
          <Field label="О компании (видят кандидаты)">
            <textarea className={inputCls} rows={3} placeholder="О компании" value={form.description || ""}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-2 content-start">
            <Field label="Телефон">
              <input className={inputCls} value={form.contact_phone || ""}
                onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
            </Field>
            <Field label="Email">
              <input className={inputCls} value={form.contact_email || ""}
                onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
            </Field>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={save} disabled={!form.company_name}>Сохранить и продолжить</Button>
          {msg && <span className="text-sm text-gray-600">{msg}</span>}
        </div>
      </Card>
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Логотип компании</h3>
        <div className="mt-2 flex items-center gap-4">
          <label className="flex h-28 w-28 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-[#d8c9ee] text-xs text-gray-400 hover:border-[#5e2b8e]">
            загрузить логотип
            <input type="file" accept="image/*" className="hidden" onChange={uploadPhoto} />
          </label>
          <p className="text-xs text-gray-400">Логотип виден кандидатам в вакансиях и приглашениях</p>
        </div>
      </Card>
    </>
  );
}

function VacanciesStep({ specs, setSpecs, skills, onDone }: any) {
  const [selected, setSelected] = useState<any>({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const toggle = (code: string) =>
    setSelected((s: any) => ({ ...s, [code]: s[code] ? undefined : {
      salary_min: 100000, salary_max: 200000, min_grade: "middle", stack: [], description: "",
      code_language: "python",
    } }));

  const setParam = (code: string, key: string, value: any) =>
    setSelected((s: any) => ({ ...s, [code]: { ...s[code], [key]: value } }));

  const addStack = (code: string, tag: string) => {
    const t = (tag || "").trim().toLowerCase();
    if (t && selected[code] && !selected[code].stack.includes(t))
      setParam(code, "stack", [...selected[code].stack, t]);
  };

  const addCustom = async (name: string) => {
    const n = (name || "").trim();
    if (!n) return;
    try {
      const r = await POST("/testing/specializations?name=" + encodeURIComponent(n));
      if (!specs.find((x: any) => x.code === r.code)) setSpecs([...specs, { code: r.code, name: n, stack_tags: [] }]);
      if (!selected[r.code]) setSelected((s: any) => ({ ...s, [r.code]: {
        salary_min: 100000, salary_max: 200000, min_grade: "middle", stack: [], description: "",
        code_language: "python",
      } }));
    } catch (e: any) { setMsg(e.message); }
  };

  const save = async () => {
    setBusy(true);
    try {
      const chosen = Object.entries(selected).filter(([, v]: any) => v) as [string, any][];
      for (const [code, v] of chosen) {
        const spec = specs.find((x: any) => x.code === code);
        await POST("/vacancies", {
          title: spec.name,
          description: v.description || spec.description,
          specialization_code: code,
          min_grade: v.min_grade,
          stack: v.stack,
          code_language: v.code_language || "python",
          salary_min: Number(v.salary_min),
          salary_max: Number(v.salary_max),
        });
      }
      onDone();
    } catch (e: any) { setMsg(e.message); setBusy(false); }
  };

  return (
    <>
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Выберите направления</h3>
        <p className="text-xs text-gray-400">Можно несколько; детали — зарплата, грейд, навыки — по желанию</p>
        <div className="mt-3 flex flex-wrap gap-1.5 mb-2">
          {Object.entries(selected).filter(([, v]: any) => v).map(([code]: any) => {
            const s = specs.find((x: any) => x.code === code);
            return (
              <button key={code} onClick={() => toggle(code)}
                className="rounded-xl bg-[#5e2b8e] px-3 py-2 text-sm font-medium text-white">
                {s ? s.name : code} ×
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <select className={inputCls} value="" onChange={(e) => toggle(e.target.value)}>
            <option value="">+ из списка ({specs.length} направлений)</option>
            {specs.filter((s: any) => !selected[s.code])
              .map((s: any) => <option key={s.code} value={s.code}>{s.name}</option>)}
          </select>
          <input id="custom-spec" className={inputCls} placeholder="или впишите своё направление"
            onKeyDown={async (e) => {
              if (e.key !== "Enter") return;
              await addCustom((e.target as HTMLInputElement).value);
              (e.target as HTMLInputElement).value = "";
            }} />
          <button onClick={async () => {
            const el = document.getElementById("custom-spec") as HTMLInputElement;
            await addCustom(el.value); el.value = "";
          }}
            className="shrink-0 rounded-xl bg-[#5e2b8e] px-3 py-2 text-sm font-medium text-white hover:bg-[#4a2172]">→</button>
        </div>
      </Card>

      {Object.entries(selected).filter(([, v]: any) => v).map(([code, v]: any) => {
        const spec = specs.find((x: any) => x.code === code);
        return (
          <Card key={code}>
            <h3 className="font-semibold text-[#3b1f5e]">{spec.name}</h3>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              <div className="grid grid-cols-2 gap-2">
                <Field label="Зарплата от, ₽">
                  <input className={inputCls} type="number" value={v.salary_min}
                    onChange={(e) => setParam(code, "salary_min", e.target.value)} />
                </Field>
                <Field label="до, ₽">
                  <input className={inputCls} type="number" value={v.salary_max}
                    onChange={(e) => setParam(code, "salary_max", e.target.value)} />
                </Field>
              </div>
              <Field label="Минимальный грейд">
                <select className={inputCls} value={v.min_grade}
                  onChange={(e) => setParam(code, "min_grade", e.target.value)}>
                  {Object.entries(GRADE_RU).map(([k, ru]) => <option key={k} value={k}>{ru}</option>)}
                </select>
              </Field>
              <Field label="Язык заданий в тесте">
                <select className={inputCls} value={v.code_language || "python"}
                  onChange={(e) => setParam(code, "code_language", e.target.value)}>
                  {["python", "javascript", "c++", "c#", "java"].map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </Field>
              <Field label="Навыки (по желанию)">
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {v.stack.map((t: string) => (
                    <button key={t} onClick={() => setParam(code, "stack", v.stack.filter((x: string) => x !== t))}
                      className="rounded-lg bg-[#5e2b8e] px-2.5 py-1 text-xs font-medium text-white">{t} ×</button>
                  ))}
                </div>
                <select className={inputCls} value="" onChange={(e) => addStack(code, e.target.value)}>
                  <option value="">+ из списка</option>
                  {skills.filter((t: string) => !v.stack.includes(t))
                    .map((t: string) => <option key={t} value={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Описание вакансии (по желанию)">
                <textarea className={inputCls} rows={2} value={v.description}
                  placeholder={spec.description}
                  onChange={(e) => setParam(code, "description", e.target.value)} />
              </Field>
            </div>
          </Card>
        );
      })}

      <div className="flex items-center gap-3">
        <Button variant="white" onClick={save} disabled={busy || !Object.values(selected).some(Boolean)}>
          {busy ? "…" : "Далее →"}
        </Button>
        {msg && <span className="text-sm text-red-600">{msg}</span>}
      </div>
    </>
  );
}

function DraftEditor({ vacancy, blueprint, allBlueprints, skills, onSaved }: any) {
  const [items, setItems] = useState<any[]>(blueprint?.items || []);
  const [skillsFound, setSkillsFound] = useState<any[]>(blueprint?.researched_skills || []);
  const [status, setStatus] = useState(blueprint ? normStatus(blueprint.status) : "нет теста");
  const [bid, setBid] = useState(blueprint?.id || null);
  const [custom, setCustom] = useState({ title: "", body: "", options: "", correct: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [seen, setSeen] = useState(false);
  const started = useRef(false);

  const build = async () => {
    setBusy(true); setErr("");
    try {
      const r = await POST("/employer/tests/draft", {
        specialization_code: vacancy.specialization_code,
        raw_text: (vacancy.stack || []).join(" ") + " " + vacancy.description,
        use_web: true,
        vacancy_id: vacancy.id,
        code_language: vacancy.code_language || "python",
      });
      setItems(r.items); setSkillsFound(r.researched_skills);
      setBid(r.blueprint_id); setStatus(normStatus(r.status) || "draft");
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  useEffect(() => {
    if (bid || started.current) return;
    started.current = true;
    (async () => {
      setBusy(true); setErr("");
      try {
        const existing = (allBlueprints || []).find((b: any) =>
          (b.vacancy_id === vacancy.id || b.specialization_code === vacancy.specialization_code) &&
          normStatus(b.status) === "draft");
        if (existing) {
          const fresh = await GET(`/employer/tests/${existing.id}`);
          setBid(existing.id); setItems(fresh.items || []);
          setSkillsFound(fresh.researched_skills || []);
          setStatus(normStatus(fresh.status) || "draft");
        } else {
          await build();
        }
      } catch (e: any) { setErr(e.message); }
      finally { setBusy(false); }
    })();
  }, []);

  const reloadItems = async () => {
    const fresh = await GET(`/employer/tests/${bid}`);
    setItems(fresh.items || []);
    if (fresh.status) setStatus(normStatus(fresh.status));
  };

  const removeItem = async (ref: string) => {
    try { await DEL(`/employer/tests/${bid}/items/${ref}`); await reloadItems(); }
    catch (e: any) { setErr(e.message); }
  };

  const addCustom = async () => {
    try {
      const opts = custom.options.split("\n").map((s: string) => s.trim()).filter(Boolean);
      await POST(`/employer/tests/${bid}/items`, {
        title: custom.title, body: custom.body, options: opts, correct: custom.correct,
      });
      setCustom({ title: "", body: "", options: "", correct: "" });
      await reloadItems();
    } catch (e: any) { setErr(e.message); }
  };

  const publish = async () => {
    try {
      const r = await POST(`/employer/tests/${bid}/publish`);
      setStatus(normStatus(r?.status) || "published");
      onSaved();
    } catch (e: any) { setErr(e.message); }
  };

  return (
    <div className="mt-3 rounded-xl border border-[#d8c9ee] bg-[#faf8fe] p-4">
      <div className="flex items-center justify-between">
        <h4 className="font-semibold text-[#3b1f5e]">Тест для «{vacancy.title}»</h4>
        <span className="text-xs text-gray-500">
          язык заданий: {vacancy.code_language || "python"} ·{" "}
          {status === "published" ? "опубликован" : status === "draft" ? "черновик" : status}
        </span>
      </div>
      {err && <p className="mt-1 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      {skillsFound.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1 text-xs">
          {skillsFound.map((s: string) => (
            <span key={s} className="rounded-full bg-[#f1e8fb] px-2 py-0.5 text-[#5e2b8e]">{s}</span>
          ))}
        </div>
      )}
      {busy && <p className="mt-2 text-sm text-gray-500">Собираем тест: ищем навыки в интернете…</p>}
      <div className="mt-2 space-y-1.5 text-sm">
        {items.map((it: any) => (
          <div key={it.ref_id} className="rounded-lg bg-white px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="font-medium text-[#3b1f5e]">
                <Badge tone={it.source === "custom" ? "green" : "purple"}>{it.source === "custom" ? "ваш" : "банк"}</Badge>{" "}
                {it.title}
              </span>
              <button className="text-xs text-red-500 shrink-0" onClick={() => removeItem(it.ref_id)}>удалить</button>
            </div>
            {it.sample?.body && (
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-gray-700">{it.sample.body}</pre>
            )}
            {it.sample?.options ? (
              <ul className="mt-1 grid gap-0.5 text-xs">
                {it.sample.options.map((o: string, i: number) => (
                  <li key={i} className={o === it.sample.answer ? "font-semibold text-green-700" : "text-gray-600"}>
                    {o === it.sample.answer ? "✓ " : "• "}{o}
                  </li>
                ))}
              </ul>
            ) : (
              it.sample?.answer && <p className="mt-1 text-xs text-gray-600">верный ответ: <b>{it.sample.answer}</b></p>
            )}
          </div>
        ))}
      </div>
      <div className="mt-2 rounded-xl bg-white p-3">
        <p className="text-sm font-medium text-[#5e2b8e]">Добавить свой вопрос</p>
        <div className="mt-1 grid gap-1.5">
          <input className={inputCls} placeholder="Название" value={custom.title}
            onChange={(e) => setCustom({ ...custom, title: e.target.value })} />
          <textarea className={inputCls} rows={2} placeholder="Текст вопроса" value={custom.body}
            onChange={(e) => setCustom({ ...custom, body: e.target.value })} />
          <textarea className={inputCls} rows={2} placeholder="Варианты (по одному на строку; пусто — свободный ответ)"
            value={custom.options} onChange={(e) => setCustom({ ...custom, options: e.target.value })} />
          <input className={inputCls} placeholder="Верный ответ" value={custom.correct}
            onChange={(e) => setCustom({ ...custom, correct: e.target.value })} />
          <Button onClick={addCustom} disabled={!custom.title || !custom.body || !custom.correct}>Добавить</Button>
        </div>
      </div>
      <div className="mt-2">
        {status !== "published" && items.length > 0 && (
          <label className="mb-2 flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" className="accent-[#5e2b8e]" checked={seen} onChange={(e) => setSeen(e.target.checked)} />
            Я посмотрел примеры вопросов
          </label>
        )}
        <Button onClick={publish} disabled={status === "published" || items.length === 0 || !seen}>
          {status === "published" ? "Тест опубликован" : "Опубликовать тест"}
        </Button>
        {status !== "published" && items.length > 0 && !seen && (
          <p className="mt-1 text-xs text-gray-400">пока галочка не стоит — публикация заблокирована</p>
        )}
      </div>
    </div>
  );
}

function TestsStep({ vacancies, blueprints, specs, onDone }: any) {
  const [saved, setSaved] = useState(false);
  return (
    <>
      {vacancies.length === 0 && (
        <Card>
          <p className="text-sm text-gray-500">Сначала добавьте вакансии</p>
          <Button variant="ghost" onClick={onDone}>← к вакансиям</Button>
        </Card>
      )}
      {vacancies.map((v: any) => (
        <DraftEditor key={v.id} vacancy={v} skills={specs} allBlueprints={blueprints}
          blueprint={findBlueprint(v, blueprints)}
          onSaved={() => { setSaved(true); onDone(); }} />
      ))}
      <div className="flex items-center gap-3">
        <Button variant="white" onClick={onDone}>Сохранить и перейти в личный кабинет</Button>
        {saved && <span className="text-sm text-emerald-600">Тесты сохранены ✓</span>}
      </div>
    </>
  );
}

function TestsTab({ vacancies, blueprints, specs, reload }: any) {
  const withTest = vacancies.filter((v: any) => findBlueprint(v, blueprints));
  const [editing, setEditing] = useState<string | null>(null);
  return (
    <>
      <p className="text-sm text-white/90">Опубликованные тесты — кандидат проходит их по приглашению. «Править» открывает состав.</p>
      <Card>
        <h3 className="font-semibold text-[#3b1f5e]">Мои тесты</h3>
        {withTest.length === 0 && <p className="mt-2 text-sm text-gray-500">Тестов ещё нет.</p>}
        <div className="mt-2 space-y-2">
          {withTest.map((v: any) => {
            const bp = findBlueprint(v, blueprints);
            return (
              <div key={v.id} className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-sm">
                <span>{bp?.title || `Тест для «${v.title}»`}
                  <span className="ml-2 text-xs text-gray-500">
                    {normStatus(bp?.status) === "published" ? "опубликован" : "черновик"}</span></span>
                <button className="text-xs text-[#5e2b8e] underline"
                  onClick={() => setEditing(editing === v.id ? null : v.id)}>
                  {editing === v.id ? "закрыть" : "править"}
                </button>
              </div>
            );
          })}
        </div>
      </Card>
      {withTest.filter((v: any) => editing === v.id).map((v: any) => (
        <DraftEditor key={v.id} vacancy={v} allBlueprints={blueprints}
          blueprint={findBlueprint(v, blueprints)}
          skills={specs} onSaved={reload} />
      ))}
    </>
  );
}

function ShortlistItems({ items, actions }: { items: any[]; actions?: (c: any) => React.ReactNode }) {
  return (
    <div className="mt-3 space-y-3">
      {(items || []).map((c: any) => (
        <div key={c.candidate_id} className="rounded-xl bg-gray-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <b className="text-[#3b1f5e]">{c.full_name}</b>
            <Badge>{c.category}</Badge>
            <span className="text-sm font-bold text-[#5e2b8e]">Score {c.score}</span>
          </div>
          <p className="mt-1 text-xs italic text-gray-600">{c.rationale}</p>
          {c.gap_note && <p className="mt-0.5 text-xs text-amber-700">Почему ниже: {c.gap_note.replace("проигрывает лидеру: ", "")}</p>}
          {c.breakdown && (
            <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
              {Object.values(c.breakdown).map((x: any) => <Bar key={x.label} label={x.label} value={x.value} />)}
            </div>
          )}
          {actions?.(c)}
        </div>
      ))}
    </div>
  );
}

function VacanciesAndShortlistTab({ vacancies, skills, blueprints, reload }: any) {
  const [open, setOpen] = useState<string | null>(null);
  const [shortlists, setShortlists] = useState<any>({});
  const [inviteFor, setInviteFor] = useState<string | null>(null);
  const [histFor, setHistFor] = useState<string | null>(null);
  const [newVac, setNewVac] = useState<any>(null);
  const [err, setErr] = useState("");

  const openShortlist = async (id: string) => {
    if (open === id) { setOpen(null); return; }
    setOpen(id);
    if (!shortlists[id]) {
      try {
        const r = await GET(`/employer/vacancy/${id}/shortlist`);
        setShortlists((s: any) => ({ ...s, [id]: r }));
      } catch (e: any) { setErr(e.message); }
    }
  };

  return (
    <>
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-[#3b1f5e]">Мои вакансии и подборка кандидатов</h3>
          <Button onClick={() => setNewVac(newVac ? null : { title: "", description: "", specialization_code: "backend", min_grade: "middle", stack: [], salary_min: 100000, salary_max: 200000 })}>
            {newVac ? "Свернуть" : "+ Новая вакансия"}
          </Button>
        </div>
        {newVac && <VacancyForm form={newVac} setForm={setNewVac} skills={skills}
          onDone={() => { setNewVac(null); reload(); }} />}
      </Card>

      {vacancies.map((v: any) => (
        <Card key={v.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <b className="text-[#3b1f5e]">{v.title}</b>
            <span className="text-sm font-medium text-[#5e2b8e]">
              {v.salary_min?.toLocaleString("ru")}–{v.salary_max?.toLocaleString("ru")} ₽
            </span>
          </div>
          <p className="text-xs text-gray-500">{v.specialization_code} · от {v.min_grade} · {v.stack?.join(", ")}</p>
          <p className="mt-1 text-sm text-[#1e1b4b]">{v.description}</p>
          <div className="mt-2 flex gap-2">
            <Button variant="ghost" onClick={() => openShortlist(v.id)}>
              {open === v.id ? "Скрыть подборку" : "Подборка кандидатов"}
            </Button>
            <Button variant="danger" onClick={async () => {
              try { await DEL(`/vacancies/${v.id}`); reload(); }
              catch (e: any) { setErr(e.message); }
            }}>
              Снять
            </Button>
          </div>
          {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
          {open === v.id && shortlists[v.id] && (
            <>
              <p className="mt-2 text-xs text-gray-400">
                подборка за {shortlists[v.id].elapsed_ms} мс · {shortlists[v.id].items.length} кандидатов
              </p>
              <ShortlistItems items={shortlists[v.id].items} actions={(c: any) => (
                <>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button onClick={() => setInviteFor(inviteFor === c.candidate_id ? null : c.candidate_id)}>
                      {inviteFor === c.candidate_id ? "Свернуть" : "Пригласить"}
                    </Button>
                    <Button variant="ghost" onClick={() => setHistFor(histFor === c.candidate_id ? null : c.candidate_id)}>
                      {histFor === c.candidate_id ? "Скрыть историю" : "История тестов"}
                    </Button>
                  </div>
                  {inviteFor === c.candidate_id && <InviteForm candidateId={c.candidate_id} vacancyId={v.id}
                    blueprints={blueprints} onDone={() => setInviteFor(null)} />}
                  {histFor === c.candidate_id && <CandidateHistory candidateId={c.candidate_id} />}
                </>
              )} />
            </>
          )}
        </Card>
      ))}
    </>
  );
}

function VacancyForm({ form, setForm, skills, onDone }: any) {
  const [err, setErr] = useState("");
  const addStack = (t: string) => {
    const x = (t || "").trim().toLowerCase();
    if (x && !form.stack.includes(x)) setForm({ ...form, stack: [...form.stack, x] });
  };
  return (
    <div className="mt-3 rounded-xl border border-[#d8c9ee] p-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Название">
          <input className={inputCls} value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field>
        <Field label="Специализация">
          <select className={inputCls} value={form.specialization_code}
            onChange={(e) => setForm({ ...form, specialization_code: e.target.value })}>
            {["backend", "frontend", "ml", "analytics", "qa", "hr", "office_admin", "devops"].map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </Field>
        <Field label="Описание">
          <textarea className={inputCls} rows={2} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Зарплата от">
            <input className={inputCls} type="number" value={form.salary_min}
              onChange={(e) => setForm({ ...form, salary_min: Number(e.target.value) })} />
          </Field>
          <Field label="до">
            <input className={inputCls} type="number" value={form.salary_max}
              onChange={(e) => setForm({ ...form, salary_max: Number(e.target.value) })} />
          </Field>
        </div>
        <Field label="Минимальный грейд">
          <select className={inputCls} value={form.min_grade}
            onChange={(e) => setForm({ ...form, min_grade: e.target.value })}>
            {Object.entries(GRADE_RU).map(([k, ru]) => <option key={k} value={k}>{ru}</option>)}
          </select>
        </Field>
        <Field label="Навыки">
          <div className="flex flex-wrap gap-1.5 mb-2">
            {form.stack.map((t: string) => (
              <button key={t} onClick={() => setForm({ ...form, stack: form.stack.filter((x: string) => x !== t) })}
                className="rounded-lg bg-[#5e2b8e] px-2.5 py-1 text-xs font-medium text-white">{t} ×</button>
            ))}
          </div>
          <select className={inputCls} value="" onChange={(e) => addStack(e.target.value)}>
            <option value="">+ из списка</option>
            {skills.filter((t: string) => !form.stack.includes(t))
              .map((t: string) => <option key={t} value={t}>{t}</option>)}
          </select>
        </Field>
      </div>
      <div className="mt-2">
        <Button onClick={async () => {
          try { await POST("/vacancies", { ...form }); onDone(); }
          catch (e: any) { setErr(e.message); }
        }} disabled={!form.title}>Опубликовать</Button>
        {err && <span className="ml-2 text-xs text-red-600">{err}</span>}
      </div>
    </div>
  );
}

function InviteForm({ candidateId, vacancyId, blueprints, onDone }: any) {
  const [form, setForm] = useState({
    message: "Ваш профиль подошёл нашей команде. Предлагаем обсудить позицию.",
    salary_min: 150000, salary_max: 250000, blueprint_id: "",
  });
  const [msg, setMsg] = useState("");
  const send = async () => {
    try {
      await POST("/invitations", {
        candidate_id: candidateId,
        vacancy_id: vacancyId,
        blueprint_id: form.blueprint_id || null,
        message: form.message,
        salary_min: Number(form.salary_min),
        salary_max: Number(form.salary_max),
      });
      setMsg("Приглашение отправлено ✓");
      setTimeout(onDone, 800);
    } catch (e: any) { setMsg(e.message); }
  };
  return (
    <div className="mt-3 rounded-xl border border-[#d8c9ee] bg-white p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Сообщение">
          <textarea className={inputCls} rows={2} value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Зарплата от, ₽">
            <input className={inputCls} type="number" value={form.salary_min}
              onChange={(e) => setForm({ ...form, salary_min: Number(e.target.value) })} />
          </Field>
          <Field label="до, ₽">
            <input className={inputCls} type="number" value={form.salary_max}
              onChange={(e) => setForm({ ...form, salary_max: Number(e.target.value) })} />
          </Field>
        </div>
        <Field label="Свой тест (необязательно)">
          <select className={inputCls} value={form.blueprint_id}
            onChange={(e) => setForm({ ...form, blueprint_id: e.target.value })}>
            <option value="">— стандартный —</option>
            {(blueprints || []).filter((b: any) => b.status === "published")
              .map((b: any) => <option key={b.id} value={b.id}>{b.title}</option>)}
          </select>
        </Field>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <Button onClick={send}>Отправить приглашение</Button>
        {msg && <span className="text-sm text-gray-600">{msg}</span>}
      </div>
    </div>
  );
}

function CandidateHistory({ candidateId }: any) {
  const [data, setData] = useState<any>(null);
  useEffect(() => { GET(`/employer/candidate/${candidateId}`).then(setData).catch(() => {}); }, [candidateId]);
  if (!data) return null;
  return (
    <div className="mt-3 rounded-xl border border-[#d8c9ee] bg-white p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {data.categories?.map((cat: any) => <Badge key={cat.category}>{cat.category}</Badge>)}
        <Badge tone={data.integrity >= 0.9 ? "green" : "gray"}>
          честность {Math.round((data.integrity || 1) * 100)}%
        </Badge>
        {data.has_fsp && <Badge tone="purple">ФСП ✓</Badge>}
      </div>
      {data.integrity < 0.8 && (
        <p className="mt-1 text-xs text-amber-700">⚠ по результатам теста были признаки посторонней помощи</p>
      )}
      {data.has_fsp && Array.isArray(data.fsp_history) && data.fsp_history.length > 0 && (
        <>
          <p className="mt-2 text-xs font-semibold text-[#5e2b8e]">Достижения ФСП (подтверждены реестром)</p>
          <FspAchievements items={data.fsp_history} />
        </>
      )}
      {data.history?.length
        ? <div className="mt-2"><HistoryBlock history={data.history} /></div>
        : <p className="mt-2 text-xs text-gray-400">История тестов пока пуста</p>}
      {data.contacts && (
        <p className="mt-2 text-sm text-emerald-700">Контакты: {JSON.stringify(data.contacts)}</p>
      )}
    </div>
  );
}

function AppsTab({ apps, reload }: any) {
  const [err, setErr] = useState("");
  const decide = async (id: string, accept: boolean) => {
    try {
      await POST(`/employer/applications/${id}/decide?accept=${accept}`);
      setErr("");
      reload();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Отклики кандидатов</h3>
      {err && <p className="mt-2 rounded-xl bg-red-50 p-2 text-sm text-red-700">{err}</p>}
      {apps.length === 0 && <p className="mt-2 text-sm text-gray-500">Откликов пока нет — кандидаты откликаются на ваши вакансии в общем списке.</p>}
      <div className="mt-3 space-y-3">
        {apps.map((a: any) => (
          <div key={a.id} className="rounded-xl bg-gray-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <b className="text-[#3b1f5e]">{a.candidate_name}</b>
              <span className="text-xs text-gray-500">на «{a.vacancy_title}»</span>
              <Badge tone={a.status === "accepted" ? "green" : a.status === "declined" ? "gray" : "purple"}>{a.status_ru || a.status}</Badge>
            </div>
            {a.cover_letter && <p className="mt-1 text-sm text-gray-600">{a.cover_letter}</p>}
            {a.candidate_contacts && (
              <p className="mt-1 text-sm text-emerald-700">Контакты: {JSON.stringify(a.candidate_contacts)}</p>
            )}
            {a.status === "sent" && (
              <div className="mt-2 flex gap-2">
                <Button onClick={() => decide(a.id, true)}>Принять</Button>
                <Button variant="danger" onClick={() => decide(a.id, false)}>Отклонить</Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function InvitesTab({ invites }: any) {
  const [taskFor, setTaskFor] = useState<string | null>(null);
  return (
    <Card>
      <h3 className="font-semibold text-[#3b1f5e]">Мои приглашения</h3>
      {invites.length === 0 && <p className="mt-2 text-sm text-gray-500">Ещё не отправлено.</p>}
      <div className="mt-3 space-y-3 text-sm">
        {invites.map((i: any) => (
          <div key={i.id} className="rounded-xl bg-gray-50 p-4">
            <div className="flex items-center justify-between">
              <span>{i.candidate_category}</span>
              <Badge tone={i.status === "accepted" ? "green" : i.status === "declined" ? "gray" : "purple"}>{i.status_ru || i.status}</Badge>
            </div>
            <p className="mt-1 text-gray-600">{i.message}</p>
            <p className="mt-1 text-[#5e2b8e]">{i.salary_min?.toLocaleString("ru")}–{i.salary_max?.toLocaleString("ru")} ₽</p>
            {i.candidate_contacts
              ? <p className="mt-1 text-emerald-700">Контакты: {JSON.stringify(i.candidate_contacts)}</p>
              : <p className="mt-1 text-xs text-gray-400">Контакты раскроются после принятия приглашения</p>}
            {i.status === "accepted" && i.candidate_id && (
              <>
                <div className="mt-2">
                  <Button variant="ghost" onClick={() => setTaskFor(taskFor === i.id ? null : i.id)}>
                    {taskFor === i.id ? "Свернуть" : "Задание"}
                  </Button>
                </div>
                {taskFor === i.id && <MicrotaskForm candidateId={i.candidate_id} onDone={() => setTaskFor(null)} />}
              </>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function MicrotaskForm({ candidateId, onDone }: any) {
  const [form, setForm] = useState({ title: "", body_text: "" });
  const [msg, setMsg] = useState("");
  const send = async () => {
    try {
      await POST("/microtasks", null, {
        candidate_id: candidateId, title: form.title, body_text: form.body_text,
      });
      setMsg("Задание отправлено ✓");
      setTimeout(onDone, 800);
    } catch (e: any) { setMsg(e.message); }
  };
  return (
    <div className="mt-2 rounded-xl border border-[#d8c9ee] bg-white p-3">
      <p className="text-sm font-medium text-[#5e2b8e]">Короткое задание кандидату</p>
      <div className="mt-1 grid gap-1.5">
        <input className={inputCls} placeholder="Название задачи" value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <textarea className={inputCls} rows={2} placeholder="Текст задания" value={form.body_text}
          onChange={(e) => setForm({ ...form, body_text: e.target.value })} />
        <div className="flex items-center gap-3">
          <Button onClick={send} disabled={!form.title || !form.body_text}>Отправить</Button>
          {msg && <span className="text-xs text-gray-600">{msg}</span>}
        </div>
      </div>
    </div>
  );
}
